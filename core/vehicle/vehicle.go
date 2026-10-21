package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type pluginInfo struct {
	obj  plugin.Plugin    // plugin object
	ln   net.Listener     // listener for plugin
	conn *grpc.ClientConn // client connection to plugin
}

type Vehicle struct {
	vehiclepb.UnimplementedDataServiceServer
	vehiclepb.UnimplementedSafetyServiceServer
	vehiclepb.UnimplementedLoaderServiceServer
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
	daemonLn   net.Listener         // daemon listener
	mainLn     net.Listener         // main socket listener
	adminLn    net.Listener         // in-process admin listener
	adminConn  *grpc.ClientConn     // admin client connection
	server     *grpc.Server         // gRPC server
	cancel     context.CancelFunc   // cancel function for active contexts
	log        zerolog.Logger       // logger object
	err        error                // error populated exactly once on a fatal error
	shutdown   chan struct{}        // shutdown channel, closed once
}

// Creates a new vehicle for a driver.
func NewVehicle(
	driver plugin.Plugin,
	driverConfig *config.PluginConfig,
	options ...VehicleOption,
) (*Vehicle, error) {
	vehicle := &Vehicle{
		Name:     uuid.New().String(),
		Config:   driverConfig,
		lawToml:  DefaultLaw,
		driver:   &pluginInfo{obj: driver},
		log:      zerolog.New(os.Stderr).With().Timestamp().Logger(),
		shutdown: make(chan struct{}, 1),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Ensure the driver config is not nil, and contains a DriverCap
	if driverConfig == nil || driverConfig.Driver == nil {
		vehicle.log.Error().Msg("driver config was nil or contained a nil driver cap")
		return nil, fmt.Errorf("driver config was nil or contained a nil driver cap")
	}

	// Set directory paths
	var err error
	vehicle.RunDir, err = util.GetVehicleRunDirByName(vehicle.Name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("directory", vehicle.RunDir).
			Msg("unable to create vehicle runtime directory")
		return nil, err
	}
	vehicle.log.Debug().Str("directory", vehicle.RunDir).
		Msg("vehicle runtime directory configured")
	vehicle.MissionDir, err = util.GetVehicleMissionDirByName(vehicle.Name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("directory", vehicle.MissionDir).
			Msg("unable to create or access vehicle mission directory")
		return nil, err
	}
	vehicle.log.Debug().Str("directory", vehicle.MissionDir).
		Msg("vehicle mission directory configured")

	// Policy and law setup
	law, err := config.ParseControlLawFromBytes(vehicle.lawToml)
	if err != nil {
		vehicle.log.Error().Err(err).Msg("could not parse law")
		return nil, err
	}
	vehicle.policy, err = policy.NewPolicy(law, policy.WithLogger(vehicle.log))
	if err != nil {
		vehicle.log.Error().Err(err).Msg("could not create policy")
		return nil, err
	}

	// Create the router
	vehicle.router = router.NewRouter(nil, nil, router.WithLogger(vehicle.log))

	// Set up gRPC servers and set up auth interceptor chain
	vehicle.server = grpc.NewServer(
		grpc.ChainUnaryInterceptor(vehicle.policy.NewUnaryPolicyInterceptor()),
		grpc.ChainStreamInterceptor(vehicle.policy.NewStreamPolicyInterceptor()),
		grpc.ForceServerCodec(router.RawCodec{}),
		grpc.UnknownServiceHandler(vehicle.router.Handle),
	)

	// Register services
	vehiclepb.RegisterDataServiceServer(vehicle.server, vehicle)
	vehiclepb.RegisterSafetyServiceServer(vehicle.server, vehicle)
	vehiclepb.RegisterLoaderServiceServer(vehicle.server, vehicle)

	return vehicle, nil
}

// Starts the vehicle but does not wait for it to stop. After a successful
// call to Start, the vehicle will keep running until it encounters a fatal
// error or the provided context is canceled.
func (v *Vehicle) Start(ctx context.Context) (err error) {
	if !v.Running.CompareAndSwap(false, true) {
		return fmt.Errorf("vehicle already running")
	}
	// A stopped vehicle can't be restarted; cleanup closes shutdown before
	// clearing Running, so a stop is always visible once the swap succeeds
	select {
	case <-v.shutdown:
		v.Running.Store(false)
		return fmt.Errorf("vehicle stopped, create a new vehicle to restart")
	default:
	}
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	v.cancel = cancel

	// Release anything acquired so far if startup fails part way through
	defer func() {
		if err != nil {
			v.Running.Store(false)
		}
	}()

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
		v.router.AddServiceRoute(s, v.driver.conn)
	}
	v.log.Info().Str("driver", v.Config.Plugin.Name).Msg("driver plugin started")

	// Serve the main and admin sockets
	main, admin := v.mainLn, v.adminLn
	go func() {
		if err := v.server.Serve(main); err != nil {
			v.log.Error().Err(err).Str("listener", "main").
				Msg("listener exited with error")
		}
	}()
	go func() {
		if err := v.server.Serve(admin); err != nil {
			v.log.Error().Err(err).Str("listener", "admin").
				Msg("listener exited with error")
		}
	}()

	// Cleanup waiter; fires when the parent context is canceled, v.cancel is
	// called, or the driver exits
	driverExit := v.driver.obj.Watch()
	go func() {
		select {
		case <-ctx.Done():
			v.log.Info().Msg("context canceled, shutting down")
		case err := <-driverExit:
			// The driver also exits when ctx is canceled, which is not fatal
			if ctx.Err() != nil {
				v.log.Info().Msg("context canceled, shutting down")
			} else if err != nil {
				v.err = fmt.Errorf("driver plugin exited: %w", err)
				v.log.Error().Err(err).Msg("driver plugin exited, shutting down")
			} else {
				v.log.Warn().Msg("driver plugin exited, shutting down")
			}
		}
		v.cleanup()
	}()

	return nil
}

// Wait blocks until the vehicle hits a fatal error.
func (v *Vehicle) Wait() error {
	select {
	case <-v.shutdown:
		return v.err
	default:
	}
	if !v.Running.Load() {
		return fmt.Errorf("vehicle not running")
	}
	<-v.shutdown
	return v.err
}

// cleanup releases any associated system resources.
func (v *Vehicle) cleanup() {
	v.server.GracefulStop()
	if err := os.RemoveAll(v.RunDir); err != nil {
		v.log.Error().Err(err).Str("directory", v.RunDir).
			Msg("failed to remove vehicle runtime directory")
	}
	close(v.shutdown)
	v.Running.Store(false)
	v.log.Info().Msg("shutdown complete")
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
