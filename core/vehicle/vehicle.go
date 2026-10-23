package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	uriel "github.com/cmusatyalab/uriel/go"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
	bolt "go.etcd.io/bbolt"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type pluginInfo struct {
	obj    plugin.Plugin      // plugin object
	ln     net.Listener       // listener for plugin
	conn   *grpc.ClientConn   // client connection to plugin
	name   string             // name of what the plugin runs, e.g. the mission file
	cancel context.CancelFunc // cancel function for the plugin's context, if it has its own
}

type Vehicle struct {
	vehiclepb.UnimplementedDataServiceServer
	vehiclepb.UnimplementedLoaderServiceServer
	missionpb.UnimplementedMissionServiceServer
	Name       string               // vehicle name
	RunDir     string               // path to vehicle runtime directory
	MissionDir string               // path to vehicle saved mission directory
	Config     *config.PluginConfig // driver plugin config
	Running    atomic.Bool          // whether of not the vehicle is currently running
	lawToml    []byte               // control law for the vehicle
	policy     *policy.Policy       // policy for command authorization
	router     *router.Router       // router to external services
	driver     *pluginInfo          // driver plugin reference
	mission    *pluginInfo          // mission plugin reference
	missionMu  sync.Mutex           // mutex to protect mission updates
	daemonLn   net.Listener         // daemon listener, given on each start
	lcsName    string               // local compute service name
	rcsAddr    string               // remote compute service address, if any
	rcsCert    []byte               // remote compute service cert in DER, if any
	engines    map[string]Engine    // engines available to dataflows, by qualified name
	uriel      *uriel.Client        // Uriel client for the vehicle's dataflows
	db         *bolt.DB             // data database, open while running
	runCtx     context.Context      // context of the current run
	dataWg     sync.WaitGroup       // telemetry reader of the current run
	flow       *dataflow            // current dataflow, if any
	flowSubs   *subscribers         // subscribers to the current dataflow, while running
	producers  map[string]bool      // producers added to the Uriel client
	flowMu     sync.Mutex           // mutex to protect dataflow updates
	mainLn     net.Listener         // main socket listener
	adminLn    net.Listener         // in-process admin listener
	adminConn  *grpc.ClientConn     // admin client connection
	server     *grpc.Server         // gRPC server
	cancel     context.CancelFunc   // cancel function for active contexts
	log        zerolog.Logger       // logger object
	mu         sync.Mutex           // mutex to protect err and shutdown
	err        error                // fatal error of the last run, if any
	shutdown   chan struct{}        // shutdown channel, closed when a run stops
}

// Creates a new vehicle for a driver.
func NewVehicle(
	driver plugin.Plugin,
	driverConfig *config.PluginConfig,
	options ...VehicleOption,
) (*Vehicle, error) {
	vehicle := &Vehicle{
		Name:      uuid.New().String(),
		Config:    driverConfig,
		lawToml:   DefaultLaw,
		driver:    &pluginInfo{obj: driver},
		lcsName:   DefaultLcsName,
		producers: make(map[string]bool),
		log:       zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Ensure the driver config is not nil, and contains a DriverCap
	if driverConfig == nil || driverConfig.Driver == nil {
		vehicle.log.Error().Msg("driver config was nil or contained a nil driver cap")
		return nil, fmt.Errorf("driver config was nil or contained a nil driver cap")
	}

	// The mission directory is persistent, so it is set up once
	var err error
	vehicle.MissionDir, err = util.GetVehicleMissionDirByName(vehicle.Name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("directory", vehicle.MissionDir).
			Msg("unable to create or access vehicle mission directory")
		return nil, err
	}
	vehicle.log.Debug().Str("directory", vehicle.MissionDir).
		Msg("vehicle mission directory configured")

	// The Uriel client lives as long as the vehicle, so its dataflow outlasts
	// a run; both compute services may start after it
	var urielOptions []uriel.ClientOption
	if vehicle.rcsAddr != "" {
		urielOptions = append(urielOptions, uriel.WithRemoteServer(vehicle.rcsAddr, vehicle.rcsCert))
	}
	vehicle.uriel, err = uriel.NewClient(vehicle.Name, vehicle.lcsName, urielOptions...)
	if err != nil {
		vehicle.log.Error().Err(err).Str("lcs", vehicle.lcsName).Str("rcs", vehicle.rcsAddr).
			Msg("could not create uriel client")
		return nil, err
	}
	vehicle.log.Debug().Str("lcs", vehicle.lcsName).Str("rcs", vehicle.rcsAddr).
		Msg("uriel client created")
	return vehicle, nil
}

// Close releases the vehicle's Uriel client, which removes its dataflow. The
// vehicle must be stopped, and can't be started again.
func (v *Vehicle) Close() error {
	if v.Running.Load() {
		return fmt.Errorf("vehicle still running")
	}
	return v.uriel.Close()
}

// Starts the vehicle but does not wait for it to stop. After a successful
// call to Start, the vehicle will keep running until it encounters a fatal
// error or the provided context is canceled. A stopped vehicle can be started
// again. The vehicle serves daemonLn, if not nil, for the daemon's calls, and
// closes it when the run stops.
func (v *Vehicle) Start(ctx context.Context, daemonLn net.Listener) (err error) {
	if !v.Running.CompareAndSwap(false, true) {
		return fmt.Errorf("vehicle already running")
	}

	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	v.cancel = cancel
	v.runCtx = ctx

	// Release anything acquired so far if startup fails part way through
	v.mainLn, v.adminLn, v.adminConn, v.daemonLn, v.db = nil, nil, nil, daemonLn, nil
	defer func() {
		if err != nil {
			v.release()
			v.Running.Store(false)
		}
	}()

	// Create the runtime directory, which is removed on shutdown
	v.RunDir, err = util.GetVehicleRunDirByName(v.Name)
	if err != nil {
		v.log.Error().Err(err).Str("directory", v.RunDir).
			Msg("unable to create vehicle runtime directory")
		return err
	}
	v.log.Debug().Str("directory", v.RunDir).
		Msg("vehicle runtime directory configured")

	// Open the data database and start recording telemetry and the results
	// of the current dataflow, if any
	if err = v.startData(ctx); err != nil {
		v.log.Error().Err(err).Msg("could not start data service")
		return err
	}

	// Policy and law setup; the policy starts each run in the law's initial state
	law, err := config.ParseControlLawFromBytes(v.lawToml)
	if err != nil {
		v.log.Error().Err(err).Msg("could not parse law")
		return err
	}
	v.policy, err = policy.NewPolicy(law, policy.WithLogger(v.log))
	if err != nil {
		v.log.Error().Err(err).Msg("could not create policy")
		return err
	}

	// Create the router; the vehicle is the end of a route, so the key a call
	// is routed here by names the vehicle itself
	v.router = router.NewRouter(nil, nil, router.WithHeaderFallback(), router.WithLogger(v.log))

	// Set up gRPC servers and set up auth interceptor chain; a stopped server
	// can't serve again, so each run gets a new one
	v.server = grpc.NewServer(
		grpc.ChainUnaryInterceptor(v.policy.NewUnaryPolicyInterceptor()),
		grpc.ChainStreamInterceptor(v.policy.NewStreamPolicyInterceptor()),
		grpc.ForceServerCodec(router.RawCodec{}),
		grpc.UnknownServiceHandler(v.router.Handle),
	)

	// Register services
	vehiclepb.RegisterDataServiceServer(v.server, v)
	vehiclepb.RegisterLoaderServiceServer(v.server, v)
	missionpb.RegisterMissionServiceServer(v.server, v)

	// Create a main socket listener with AuthCode ExternalCode; the main
	// socket is a general endpoint for arbitrary entities to make API calls to
	// the vehicle
	mainSocketPath := filepath.Join(v.RunDir, MainSocketName)
	ln, err := createUnixSocketListener(mainSocketPath)
	if err != nil {
		v.log.Error().Err(err).Str("path", mainSocketPath).
			Msg("failed to create socket listener for main services")
		return err
	}
	v.mainLn = listener.NewCodedListener(ln, listener.NewAcl(nil, nil, true))

	// Create an in-process admin listener with AuthCode AdminCode; it is only
	// reachable by this process, so plugins and other processes can't use it
	adminLn := listener.NewLocalListener(listener.AdminCode)
	v.adminLn = adminLn
	v.adminConn, err = grpc.NewClient(
		"passthrough:///admin",
		grpc.WithContextDialer(adminLn.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		v.log.Error().Err(err).Msg("failed to create admin client connection")
		return err
	}
	// Start the driver and configure the router to point to it
	v.log.Info().Str("driver", v.Config.Plugin.Name).Msg("starting driver plugin")
	v.driver.ln, v.driver.conn, err = v.driver.obj.Start(ctx) // driver listener is unused, it is a pure server
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
		return err
	}
	for _, s := range v.Config.Driver.Supported.Services {
		// The stream service is internal and thus not globally hosted
		if strings.ReplaceAll(s, ".", "/") == StreamService {
			continue
		}
		v.router.AddServiceRoute(s, v.driver.conn)
	}
	v.log.Info().Str("driver", v.Config.Plugin.Name).Msg("driver plugin started")

	// The driver streams telemetry on every run, and the current dataflow's
	// cameras, if any, since a restarted driver streams nothing
	err = v.streamTelemetry(ctx)
	if err == nil {
		v.flowMu.Lock()
		if v.flow != nil {
			err = v.streamCameras(ctx, v.flow.cameras)
		}
		v.flowMu.Unlock()
	}
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver streams, aborting")
		// Wait for the driver to stop, so the vehicle can be started again
		v.cancel()
		v.driver.obj.Wait()
		return err
	}

	// Serve the main and admin sockets
	server, main, admin, daemon := v.server, v.mainLn, v.adminLn, v.daemonLn
	go func() {
		if err := server.Serve(main); err != nil {
			v.log.Error().Err(err).Str("listener", "main").
				Msg("listener exited with error")
		}
	}()
	go func() {
		if err := server.Serve(admin); err != nil {
			v.log.Error().Err(err).Str("listener", "admin").
				Msg("listener exited with error")
		}
	}()
	if daemon != nil {
		go func() {
			if err := server.Serve(daemon); err != nil {
				v.log.Error().Err(err).Str("listener", "daemon").
					Msg("listener exited with error")
			}
		}()
	}

	// Start of a new run, which Wait blocks on until cleanup closes shutdown
	shutdown := make(chan struct{})
	v.mu.Lock()
	v.shutdown = shutdown
	v.err = nil
	v.mu.Unlock()

	// Cleanup waiter; fires when the parent context is canceled, v.cancel is
	// called, or the driver exits
	driverExit := v.driver.obj.Watch()
	go func() {
		var runErr error
		select {
		case <-ctx.Done():
			v.log.Info().Msg("context canceled, shutting down")
			// Wait for the driver to finish its own cleanup, so that it can be
			// started again as soon as the vehicle has stopped
			if driverExit != nil {
				<-driverExit
			}
		case err := <-driverExit:
			// The driver also exits when ctx is canceled, which is not fatal
			if ctx.Err() != nil {
				v.log.Info().Msg("context canceled, shutting down")
			} else if err != nil {
				runErr = fmt.Errorf("driver plugin exited: %w", err)
				v.log.Error().Err(err).Msg("driver plugin exited, shutting down")
			} else {
				v.log.Warn().Msg("driver plugin exited, shutting down")
			}
		}
		v.cleanup(shutdown, runErr)
	}()

	return nil
}

// Wait blocks until the vehicle stops, and returns the fatal error that
// stopped it, if any. If the vehicle has already stopped, Wait returns
// immediately.
func (v *Vehicle) Wait() error {
	v.mu.Lock()
	shutdown := v.shutdown
	v.mu.Unlock()
	if shutdown == nil {
		return fmt.Errorf("vehicle not running")
	}
	<-shutdown
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.err
}

// cleanup releases any associated system resources once the driver has
// exited, then marks the run as stopped with its fatal error, if any.
func (v *Vehicle) cleanup(shutdown chan struct{}, err error) {
	// The mission is stopped first, since its calls would hold up the server
	v.missionMu.Lock()
	v.stopMission()
	v.missionMu.Unlock()
	v.server.GracefulStop()
	v.release()
	v.mu.Lock()
	v.err = err
	close(shutdown)
	v.mu.Unlock()
	// Cleared after closing shutdown, so a new run never sees the old channel
	v.Running.Store(false)
	v.log.Info().Msg("shutdown complete")
}

// release closes the listeners and connections created by Start, cancels the
// run context, and removes the runtime directory.
func (v *Vehicle) release() {
	if v.adminConn != nil {
		v.adminConn.Close()
	}
	if v.adminLn != nil {
		v.adminLn.Close()
	}
	if v.mainLn != nil {
		v.mainLn.Close()
	}
	if v.daemonLn != nil {
		v.daemonLn.Close()
	}
	v.cancel()
	v.stopData()
	if v.RunDir != "" {
		if err := os.RemoveAll(v.RunDir); err != nil {
			v.log.Error().Err(err).Str("directory", v.RunDir).
				Msg("failed to remove vehicle runtime directory")
		}
	}
}

// createUnixSocketListener builds a UDS listener from a filepath.
func createUnixSocketListener(path string) (net.Listener, error) {
	os.RemoveAll(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("can't listen at file %s: %w", path, err)
	}
	return ln, nil
}
