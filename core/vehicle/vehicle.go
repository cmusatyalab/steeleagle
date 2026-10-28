package vehicle

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"sync"
	"sync/atomic"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	uriel "github.com/cmusatyalab/uriel/go"
	"github.com/rs/zerolog"
	"go.etcd.io/bbolt"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// pluginInfo holds the connection to a plugin.
type pluginInfo struct {
	ln     net.Listener
	conn   *grpc.ClientConn
	cancel context.CancelFunc // stops the plugin (nil if it stops with the vehicle)
}

// computeInfo holds compute info for the vehicle.
type computeInfo struct {
	lcs  string // lcs name
	rcs  string // rcs address (host:port), empty if none
	cert []byte // rcs certificate
}

// flowInfo holds flow info for the vehicle's current dataflow.
type flowInfo struct {
	name string             // current flow name
	spec []byte             // current flow spec in bytes
	flow *config.FlowConfig // current flow config
	mu   sync.Mutex         // mutex
}

// streamInfo holds info on the names for all producer streams.
type streamInfo struct {
	telemetry string   // telemetry producer name
	cameras   []string // camera producer names
}

// EngineInfo is info about a particular engine.
type EngineInfo struct {
	Config *config.PluginConfig // engine config
	Local  bool                 // whether or not the engine is local
}

// EngineMap is a map of all available engines.
type EngineMap map[string]*EngineInfo

// Vehicle is a SteelEagle vehicle. It is responsible for monitoring a driver,
// and managing permissions for local missions. Start, Wait and Close rely on
// daemon locking, but its services are called concurrently, so the state they
// share has its own locks.
type Vehicle struct {
	vehiclepb.UnimplementedDataServiceServer
	vehiclepb.UnimplementedLoaderServiceServer
	vehiclepb.UnimplementedSafetyServiceServer
	missionpb.UnimplementedMissionServiceServer
	Name            string                     // vehicle name
	MissionDir      string                     // mission directory
	running         atomic.Bool                // whether or not the vehicle is running
	runDir          string                     // run directory
	failsafe        vehiclepb.FailsafeState    // failsafe state
	failsafeTime    time.Time                  // time of the last failsafe state change
	controlBehavior vehiclepb.FailsafeBehavior // failsafe behavior for control loss
	dataBehavior    vehiclepb.FailsafeBehavior // failsafe behavior for data loss
	safetyMu        sync.Mutex                 // mutex for the failsafe state and behaviors
	conn            *grpc.ClientConn           // admin client conn to local services
	adminLn         *listener.LocalListener    // admin listener
	daemonLn        *listener.LocalListener    // daemon listener (for callouts)
	daemonConn      *grpc.ClientConn           // conn to the daemon over daemonLn, the router's upstream
	driver          plugin.Plugin              // driver plugin
	driverInfo      *pluginInfo                // driver connections
	streamInfo      *streamInfo                // information about the driver streams
	config          *config.PluginConfig       // driver plugin config
	mission         plugin.Plugin              // mission plugin (starts empty)
	missionName     string                     // file name of the loaded mission
	missionInfo     *pluginInfo                // mission connections
	missionMu       sync.Mutex                 // mutex for mission, missionName, and missionInfo
	policy          *policy.Policy             // policy for the vehicle
	router          *router.Router             // service router
	server          *grpc.Server               // gRPC server
	engines         EngineMap                  // map of available engines
	flowInfo        *flowInfo                  // information about the current flow
	compute         *computeInfo               // information about compute servers
	db              *bbolt.DB                  // bbolt database
	dataWg          sync.WaitGroup             // goroutines storing data in db
	uriel           *uriel.Client              // uriel client reference
	auth            listener.AuthCode          // auth code of calls from the vehicle to the daemon
	ctx             context.Context            // context for the vehicle
	cancel          context.CancelFunc         // cancel function for active contexts
	shutdown        chan struct{}              // shutdown channel, closed when a run stops
	err             error                      // why the last run stopped, if not canceled
	log             zerolog.Logger             // logger object
	out             io.Writer                  // stream the mission's stdout and stderr are written to
}

// NewVehicle creates a new vehicle that wraps `driver`, configured by its plugin
// config. Only what persists across runs, like the mission directory, is set up
// here; Start sets up the rest for each run, and a stopped run holds nothing,
// so the vehicle can be started again any number of times.
func NewVehicle(
	driver plugin.Plugin,
	config *config.PluginConfig,
	options ...VehicleOption,
) (*Vehicle, error) {
	vehicle := &Vehicle{
		Name:            util.ShortId(),
		failsafe:        vehiclepb.FailsafeState_FAILSAFE_STATE_NONE,
		failsafeTime:    time.Now(),
		controlBehavior: vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD,
		dataBehavior:    vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_NONE,
		driver:          driver,
		config:          config,
		flowInfo:        &flowInfo{},
		compute: &computeInfo{
			lcs: DefaultLcsName,
		},
		log: zerolog.New(os.Stderr).With().Timestamp().Logger(),
		out: os.Stderr,
	}
	for _, option := range options {
		option(vehicle)
	}

	// Ensure the driver config is not nil, and contains a DriverCap
	if config == nil || config.Driver == nil {
		vehicle.log.Error().Msg("driver config was nil or contained a nil driver cap")
		return nil, fmt.Errorf("driver config was nil or contained a nil driver cap")
	}

	// The mission directory is persistent, so it is set up once
	var err error
	if vehicle.MissionDir == "" {
		vehicle.MissionDir, err = util.GetVehicleMissionDirByName(vehicle.Name)
		if err != nil {
			vehicle.log.Error().Err(err).Str("directory", vehicle.MissionDir).
				Msg("unable to create or access vehicle mission directory")
			return nil, err
		}
	}
	vehicle.log.Debug().Str("directory", vehicle.MissionDir).
		Msg("vehicle mission directory configured")

	// Build stream info; the producers are taken by each run's Uriel client
	vehicle.streamInfo = &streamInfo{}
	vehicle.streamInfo.telemetry = vehicle.producerUri(TelemetryProducerName)
	for _, camera := range config.Driver.Cameras {
		vehicle.streamInfo.cameras = append(vehicle.streamInfo.cameras, vehicle.producerUri(camera.Name))
	}

	return vehicle, nil
}

// Start starts the vehicle and its driver with the provided context. Returns
// a listener for the vehicle to call out, a connection to talk to the vehicle,
// or a startup error if encountered. The run stops when ctx is canceled or the
// driver exits, and Wait waits for it to.
func (v *Vehicle) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	if !v.running.CompareAndSwap(false, true) {
		return nil, nil, fmt.Errorf("vehicle already running")
	}

	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	v.cancel = cancel
	v.ctx = ctx
	v.shutdown = make(chan struct{})
	v.err = nil

	// Automatically clean up resources if an error was encountered
	var err error
	defer func() {
		if err != nil {
			v.release()
			v.running.Store(false)
			close(v.shutdown)
		}
	}()

	// Create the runtime directory, which is removed on shutdown
	v.runDir, err = util.GetVehicleRunDirByName(v.Name)
	if err != nil {
		v.log.Error().Err(err).Str("directory", v.runDir).
			Msg("unable to create vehicle runtime directory")
		return nil, nil, err
	}
	v.log.Debug().Str("directory", v.runDir).
		Msg("vehicle runtime directory configured")

	// Policy and law setup
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		v.log.Error().Err(err).Msg("could not parse law")
		return nil, nil, err
	}
	v.policy, err = policy.NewPolicy(law, policy.WithLogger(v.log))
	if err != nil {
		v.log.Error().Err(err).Msg("could not create policy")
		return nil, nil, err
	}

	// Create a listener with auth for callouts to the daemon, and a conn the
	// vehicle calls out with
	v.daemonLn = listener.NewLocalListener(v.auth)
	v.daemonConn, err = grpc.NewClient(
		"passthrough:///daemon",
		grpc.WithContextDialer(v.daemonLn.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		v.log.Error().Err(err).Msg("failed to create connection to the daemon")
		return nil, nil, err
	}

	// Create the router; the vehicle is the end of a route, so calls with its
	// own key go to the driver, and calls with any other key, like a mission's
	// calls to other services, go out through the daemon
	v.router = router.NewRouter(nil, nil,
		router.WithUpstream(v.Name, v.daemonConn),
		router.WithLogger(v.log),
	)

	// Set up gRPC servers and set up auth interceptor chain; a stopped server
	// can't serve again, so each run gets a new one
	v.server = grpc.NewServer(
		grpc.ChainUnaryInterceptor(v.policy.NewUnaryPolicyInterceptor()),
		grpc.ChainStreamInterceptor(
			v.policy.NewStreamPolicyInterceptor(),
			v.newDmsInterceptor(ctx), // dead man's switch
		),
		grpc.ForceServerCodec(router.RawCodec{}),
		grpc.UnknownServiceHandler(v.router.Handle),
	)

	// Register services
	vehiclepb.RegisterDataServiceServer(v.server, v)
	vehiclepb.RegisterLoaderServiceServer(v.server, v)
	vehiclepb.RegisterSafetyServiceServer(v.server, v)
	missionpb.RegisterMissionServiceServer(v.server, v)

	// Create an admin conn served by the vehicle
	v.adminLn = listener.NewLocalListener(listener.AdminCode)
	v.conn, err = grpc.NewClient(
		"passthrough:///admin",
		grpc.WithContextDialer(v.adminLn.Dial),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		v.log.Error().Err(err).
			Msg("failed to create daemon admin connection to main services")
		return nil, nil, err
	}

	// Start the driver and configure the router to point to it
	v.log.Info().Str("driver", v.config.Plugin.Name).Msg("starting driver plugin")
	ln, conn, err := v.driver.Start(ctx) // driver listener is unused, it is a pure server
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
		return nil, nil, err
	}
	v.driverInfo = &pluginInfo{ln: ln, conn: conn}
	for _, s := range v.config.Driver.Supported.Services {
		v.router.AddServiceRoute(s, v.driverInfo.conn)
	}
	v.log.Info().Str("driver", v.config.Plugin.Name).Msg("driver plugin started")

	// Create the Uriel client, and take the inputs of every producer the
	// driver can stream, so that any of them can be used in a flow
	err = v.openUriel()
	if err != nil {
		v.log.Error().Err(err).Str("lcs", v.compute.lcs).Str("rcs", v.compute.rcs).
			Msg("could not create uriel client, aborting")
		return nil, nil, err
	}

	// Open the datastore before telemetry is streamed, so none is missed
	err = v.openDatastore()
	if err != nil {
		v.log.Error().Err(err).Msg("could not start open datastore, aborting")
		return nil, nil, err
	}

	// Stream telemetry from the driver
	err = v.streamTelemetry(ctx)
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver streams, aborting")
		return nil, nil, err
	}

	// Serve listener
	go func() {
		if err := v.server.Serve(v.adminLn); err != nil {
			v.log.Error().Err(err).Str("listener", "admin").
				Msg("listener exited with error")
		}
	}()

	go v.run(ctx)
	return v.daemonLn, v.conn, nil
}

// run waits for the run to stop, when ctx is canceled or the driver exits,
// and releases it.
func (v *Vehicle) run(ctx context.Context) {
	var err error
	select {
	case <-ctx.Done():
	case err = <-v.driver.Watch():
		if err == nil {
			err = errors.New("driver exited")
		}
		v.log.Error().Err(err).Msg("driver exited, stopping vehicle")
	}
	v.release()
	v.err = err
	v.running.Store(false)
	close(v.shutdown)
}

// Wait waits for the current run of the vehicle to stop, and returns why it
// stopped if it wasn't canceled, like the driver's exit error. It returns
// right away if the vehicle was never started.
func (v *Vehicle) Wait() error {
	if v.shutdown == nil {
		return nil
	}
	<-v.shutdown
	return v.err
}

// openUriel creates then runs Uriel client, which takes the inputs of every
// producer the driver can stream.
func (v *Vehicle) openUriel() error {
	var options []uriel.ClientOption
	if v.compute.rcs != "" {
		options = append(options, uriel.WithRemoteServer(v.compute.rcs, v.compute.cert))
	}
	var err error
	v.uriel, err = uriel.NewClient(v.Name, v.compute.lcs, options...)
	if err != nil {
		return err
	}
	for _, producer := range append([]string{v.streamInfo.telemetry}, v.streamInfo.cameras...) {
		if err := v.uriel.AddProducer(producer); err != nil {
			return err
		}
	}
	return nil
}

// release frees everything a run allocated, whether it started fully or not.
func (v *Vehicle) release() {
	v.cancel()
	if v.server != nil {
		// Calls are canceled rather than waited for, so that a slow one, like
		// an upload, doesn't hold up the stop
		v.server.Stop()
	}
	v.missionMu.Lock()
	v.stopMission()
	v.missionMu.Unlock()
	if v.db != nil {
		v.dataWg.Wait()
		v.db.Close()
		v.db = nil
	}
	// Closing the Uriel client removes its flow, and the datastore starts
	// empty, so each run starts without a dataflow
	v.flowInfo.mu.Lock()
	if v.uriel != nil {
		if err := v.uriel.Close(); err != nil {
			v.log.Error().Err(err).Msg("could not close uriel client")
		}
		v.uriel = nil
	}
	v.flowInfo.name, v.flowInfo.spec, v.flowInfo.flow = "", nil, nil
	v.flowInfo.mu.Unlock()
	if v.driverInfo != nil { // driver has been set before
		v.driver.Wait()
		v.driverInfo.conn.Close()
		v.driverInfo = nil
	}
	for _, c := range []*grpc.ClientConn{v.conn, v.daemonConn} {
		if c != nil {
			c.Close()
		}
	}
	for _, ln := range []*listener.LocalListener{v.adminLn, v.daemonLn} {
		if ln != nil {
			ln.Close()
		}
	}
	v.conn, v.daemonConn, v.adminLn, v.daemonLn = nil, nil, nil, nil
	if v.runDir != "" {
		os.RemoveAll(v.runDir)
		v.runDir = ""
	}
}
