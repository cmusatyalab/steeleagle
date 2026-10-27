package vehicle

import (
	"context"
	"fmt"
	"net"
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
	"github.com/rs/zerolog"
	"go.etcd.io/bbolt"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// pluginInfo holds the connection to a plugin.
type pluginInfo struct {
	ln   net.Listener
	conn *grpc.ClientConn
}

// computeInfo holds compute info for the vehicle.
type computeInfo struct {
	lcs  string // lcs endpoint
	rcs  string // rcs endpoint
	port string // rcs port
	cert string // rcs certificate
}

// Vehicle is a SteelEagle vehicle. It is responsible for monitoring a driver,
// and managing permissions for local missions. Vehicle methods are not generally
// threadsafe, and rely on daemon locking to prevent race conditions.
type Vehicle struct {
	Name        string                     // vehicle name
	MissionDir  string                     // mission directory
	running     atomic.Bool                // whether or not the vehicle is running
	runDir      string                     // run directory
	failsafe    vehiclepb.FailsafeState    // failsafe state
	behavior    vehiclepb.FailsafeBehavior // failsafe behavior
	conn        *grpc.ClientConn           // admin client conn to local services
	adminLn     net.Listener               // admin listener
	daemonLn    net.Listener               // daemon listener (for callouts)
	driver      plugin.Plugin              // driver plugin
	driverInfo  *pluginInfo                // driver connections
	streamInfo  *streamInfo                // information about the driver streams
	config      *config.PluginConfig       // driver plugin config
	mission     plugin.Plugin              // mission plugin (starts empty)
	missionInfo *pluginInfo                // mission connections
	policy      *policy.Policy             // policy for the vehicle
	router      *router.Router             // service router
	server      *grpc.Server               // gRPC server
	engines     EngineMap                  // map of available engines
	flowInfo    *flowInfo                  // information about the current flow
	compute     *computeInfo               // information about compute servers
	db          *bbolt.DB                  // bbolt database
	uriel       *uriel.Client              // uriel client reference
	auth        listener.AuthCode          // auth code of calls from the vehicle to the daemon
	ctx         context.Context            // context for the vehicle
	cancel      context.CancelFunc         // cancel function for active contexts
	shutdown    chan struct{}              // shutdown channel, closed when a run stops
	log         zerolog.Logger             // logger object
}

// NewVehicle creates a new vehicle that wraps `driver`. Start must be able to be called
// multiple times to support restarts, so all ephemeral
func NewVehicle(
	driver plugin.Plugin,
	config *config.PluginConfig,
	options ...VehicleOption,
) (*Vehicle, error) {
	vehicle := &Vehicle{
		Name: util.ShortId(),
		flow: &flowInfo{},
		compute: &computeInfo{
			lcs: DefaultLcsName,
		},
		log: zerolog.Logger(),
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

	// Create the uriel client, since it persists with the vehicle
	var urielOptions []uriel.ClientOption
	if vehicle.compute.rcs != "" {
		urielOptions = append(
			urielOptions,
			uriel.WithRemoteServer(vehicle.compute.rcs+':'+vehicle.compute.port, vehicle.compute.cert),
		)
	}
	vehicle.uriel, err = uriel.NewClient(vehicle.Name, vehicle.compute.lcs, urielOptions...)
	if err != nil {
		vehicle.log.Error().Err(err).Str("lcs", vehicle.compute.lcs).Str("rcs", vehicle.compute.rcs).
			Msg("could not create uriel client")
		return nil, err
	}
	vehicle.log.Debug().Str("lcs", vehicle.compute.lcs).Str("rcs", vehicle.compute.rcs).
		Msg("uriel client created")
	return vehicle, nil
}

// Start starts the vehicle and its driver with the provided context. Returns
// a listener for the vehicle to call out, a connection to talk to the vehicle,
// or a startup error if encountered.
func (v *Vehicle) Start(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
	if !v.Running.CompareAndSwap(false, true) {
		return nil, nil, fmt.Errorf("vehicle already running")
	}

	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	v.cancel = cancel
	v.ctx = ctx

	// Automatically clean up resources if an error was encountered
	var err error
	defer func() {
		if err != nil {
			v.release()
			v.Running.Store(false)
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
		grpc.ChainUnaryInterceptor(
			v.policy.NewUnaryPolicyInterceptor(),
			newDmsInterceptor(), // dead man's switch
		),
		grpc.ChainStreamInterceptor(v.policy.NewStreamPolicyInterceptor()),
		grpc.ForceServerCodec(router.RawCodec{}),
		grpc.UnknownServiceHandler(v.router.Handle),
	)

	// Register services
	vehiclepb.RegisterDataServiceServer(v.server, v)
	vehiclepb.RegisterLoaderServiceServer(v.server, v)
	missionpb.RegisterMissionServiceServer(v.server, v)

	// Create a listener with auth for callouts to the daemon
	v.daemonLn = listener.NewLocalListener(v.auth)
	// Create an admin conn served by the vehicle
	v.adminLn = listener.NewLocalListener(listener.AdminCode)
	v.conn, err := grpc.NewClient(
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
	v.driverInfo.ln, v.driverInfo.conn, err = v.driver.Start(ctx) // driver listener is unused, it is a pure server
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
		return nil, nil, err
	}
	for _, s := range v.config.Driver.Supported.Services {
		v.router.AddServiceRoute(s, v.driverInfo.conn)
	}
	v.log.Info().Str("driver", v.config.Plugin.Name).Msg("driver plugin started")

	// Stream telemetry from the driver
	err = v.streamTelemetry(ctx)
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver streams, aborting")
		return nil, nil, err
	}

	// Serve listener
	go func() {
		if err := server.Serve(v.adminLn); err != nil {
			v.log.Error().Err(err).Str("listener", "admin").
				Msg("listener exited with error")
		}
	}()

	return v.daemonLn, v.conn, nil
}

// Wait waits for a vehicle to shut down.
func (v *Vehicle) Wait() {
	if v.shutdown == nil {
		return
	}
	<-v.shutdown
}

// release frees all vehicle allocations.
func (v *Vehicle) release() {
	v.cancel()
	v.server.GracefulStop()
	if v.driverInfo != nil { // driver has been set before
		v.driver.Wait()
		v.driverInfo.conn.Close()
	}
	if v.missionInfo != nil { // mission has been set before
		v.mission.Wait()
		v.missionInfo.conn.Close()
	}
	if v.conn != nil {
		v.conn.Close()
	}
	if v.adminLn != nil {
		v.adminLn.Close()
	}
}
