package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"slices"
	"sync/atomic"
	"time"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type Vehicle struct {
	Name          string                  // vehicle name
	Model         string                  // vehicle hardware model, reported by the driver
	RunDir        string                  // path to vehicle runtime directory
	running       atomic.Bool             // whether or not the vehicle is currently running
	pluginCfg     PluginConfig            // plugin configuration
	policyCfg     PolicyConfig            // policy configuration
	videoCfg      VideoStreamConfig       // video stream config
	gabrielCfg    GabrielConfig           // Gabriel config
	policy        policyState             // active policy state
	driver        *grpc.ClientConn        // driver gRPC client connection
	mission       *grpc.ClientConn        // mission gRPC client connection
	listeners     map[string]net.Listener // map of names to active listeners
	services      *grpc.Server            // gRPC server instance
	log           zerolog.Logger          // logger object
	gabrielClient gabrielclient.Client    // Gabriel remote server client
	store         *dataStore              // data store
	pluginMonitor *pluginMonitor          // pluginMonitor
	cancelFn      context.CancelFunc      // cancel function for vehicle context
	err           error                   // vehicle error, populated exactly once when a fatal error occurs
	shutdown      chan struct{}           // shutdown channel
}

// Create a new vehicle with the given plugins and options.
func NewVehicle(
	pluginCfg PluginConfig,
	options ...VehicleOption) (*Vehicle, error) {
	if pluginCfg.Driver == nil {
		return nil, fmt.Errorf("no driver provided, aborting")
	}

	// Set default input options and retrieve options
	vehicle := &Vehicle{
		Name:      uuid.New().String(),
		listeners: make(map[string]net.Listener),
		pluginCfg: pluginCfg,
		log:       zerolog.New(os.Stderr).With().Timestamp().Logger(),
		shutdown:  make(chan struct{}, 1),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Create the runtime directory
	var err error
	vehicle.RunDir, err = util.GetVehicleDirByName(vehicle.Name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("folder", vehicle.RunDir).
			Msg("Unable to create vehicle directory")
		return nil, err
	}
	vehicle.log.Debug().Str("folder", vehicle.RunDir).
		Msg("vehicle folder configured")

	// Set up law handling
	vehicle.policy = getPolicy(vehicle.policyCfg)

	// Set up gRPC servers and set up auth interceptor chain
	vehicle.services = grpc.NewServer(
		grpc.StreamInterceptor(vehicle.getInterceptor()),
		grpc.CustomCodec(proxy.Codec()),
		grpc.UnknownServiceHandler(proxy.TransparentHandler(
			vehicle.getProxyDirector(),
		)),
	)

	// Initialize data store
	vehicle.store, err = newDataStore(vehicle.RunDir)
	if err != nil {
		vehicle.log.Err(err).Msg("error creating data store")
		return nil, err
	}

	// Register data service
	vehiclepb.RegisterDataServiceServer(
		vehicle.services,
		&DataService{store: vehicle.store},
	)

	return vehicle, nil
}

// Starts the vehicle but does not wait for it to stop. After a successful
// call to Start, the vehicle will keep running until it encounters a fatal
// error or the provided context is canceled.
func (v *Vehicle) Start(ctx context.Context) error {
	if !v.running.CompareAndSwap(false, true) {
		return fmt.Errorf("vehicle already running")
	}
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	v.cancelFn = cancel

	// Create a main socket listener with AuthCode ExternalCode. The main
	// socket is a general endpoint for arbitrary entities to make API calls to
	// the vehicle
	var err error
	mainSocketPath := filepath.Join(v.RunDir, MainSocketName)
	ln, err := createUnixSocketListener(mainSocketPath)
	if err != nil {
		v.log.Error().Err(err).Str("path", mainSocketPath).
			Msg("failed to create socket listener for main services")
		cancel()
		return err
	}
	v.listeners[MainListenerName] =
		util.NewCodedListener(ln, util.ExternalCode, nil)

	// Create an admin socket listener with AuthCode AdminCode. The admin
	// socket is intended for use by this process
	adminSocketPath := filepath.Join(v.RunDir, AdminSocketName)
	ln, err = createUnixSocketListener(adminSocketPath)
	if err != nil {
		v.log.Error().Err(err).Str("path", mainSocketPath).
			Msg("failed to create socket listener for admin services")
		cancel()
		return err
	}
	v.listeners[AdminListenerName] =
		util.NewCodedListener(
			ln,
			util.AdminCode,
			util.GetACL(nil, []int{os.Getpid()}),
		)

	// Start driver plugin
	_, v.driver, err = v.pluginCfg.Driver.Start(ctx)
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
		cancel()
		return err
	}
	v.log.Debug().Msgf("driver plugin %s started!", v.pluginCfg.Driver.Name())

	// Query the driver for its hardware model before registering with Gabriel.
	// Not every driver implements InfoService, so a failure here is non-fatal;
	// the vehicle just registers with an empty model.
	if model, err := v.getDriverModel(ctx); err != nil {
		v.log.Warn().Err(err).Msg("could not get vehicle model from driver")
	} else {
		v.Model = model
	}

	// Start mission plugin
	if v.pluginCfg.Mission == nil {
		v.log.Debug().Msg("no mission provided, continuing with no mission")
	} else {
		ln, v.mission, err = v.pluginCfg.Mission.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).
				Msg("could not start mission plugin, aborting")
			cancel()
			return err
		}
		// For logging purposes, use a mission tag instead of the name to
		// disambiguate between this plugin and external plugins
		v.listeners[MissionListenerName] = ln
		v.log.Debug().
			Msgf("mission plugin %s started!", v.pluginCfg.Mission.Name())
	}

	// Start all other plugins
	for _, plugin := range v.pluginCfg.Plugins {
		ln, _, err = plugin.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).
				Msgf("could not start plugin %s, aborting", plugin.Name())
			cancel()
			return err
		}
		if ln != nil &&
			!slices.Contains(ReservedNames, plugin.Name()) &&
			!slices.Contains(ReservedCodes, plugin.Code()) {
			v.listeners[plugin.Name()] = ln
		} else {
			v.log.Debug().
				Msgf("plugin %s listener not added: doesn't exist or has a reserved name/code", plugin.Name())
		}
		v.log.Debug().Msgf("plugin %s started!", plugin.Name())
	}

	// reset plugin state if a plugin exists and is restarted
	pluginResetCb := func(
		pluginType pluginType,
		pluginName string,
		ln net.Listener,
		conn *grpc.ClientConn) {

		switch pluginType {
		case driverPlugin:
			v.driver = conn
		case missionPlugin:
			v.mission = conn
			v.listeners[MissionListenerName] = ln
		default:
			v.listeners[pluginName] = ln
		}
	}

	// Monitor plugins in case they exit unexpectedly, restarting them with
	// backoff so a crashed driver or mission plugin comes back on its own
	// instead of leaving the vehicle running against a dead plugin.
	v.pluginMonitor = &pluginMonitor{
		pluginCfg:     v.pluginCfg,
		restartPolicy: alwaysRestart,
		log:           v.log,
		pluginResetCb: pluginResetCb,
	}
	v.pluginMonitor.start(ctx)

	// Serve the gRPC server at all listeners
	for name, ln := range v.listeners {
		go func() {
			// Serve in a loop to account for plugin restarts that might cause
			// Serve() to fail. Back off between retries so we don't busy-loop.
			backoff := initialRestartBackoff
			for {
				if err := v.services.Serve(ln); err != nil {
					v.log.Error().Err(err).Str("listener", name).
						Dur("retry_in", backoff).
						Msg("listener exited with error, retrying")
				}
				if ctx.Err() != nil || v.err != nil {
					break
				}
				select {
				case <-time.After(backoff):
				case <-ctx.Done():
					return
				}
				backoff *= 2
				if backoff > maxRestartBackoff {
					backoff = maxRestartBackoff
				}
			}
		}()
	}

	// Start streaming frames and telemetry from the driver
	v.startDriverStreaming(ctx)

	// Initialize the store, launching goroutine to flush telemetry data to
	// disk periodically
	v.store.init(ctx)

	// Create gabriel client with telemetry and frame producers if a server
	// endpoint is specified
	if v.gabrielCfg.ServerEndpoint != "" {
		err = v.createGabrielClient()
		if err != nil {
			v.log.Err(err).Msg("failed to create Gabriel client")
			cancel()
			return err
		}
		_, err = v.gabrielClient.Launch(ctx)
		if err != nil {
			v.log.Err(err).Msg("failed to launch Gabriel client")
			cancel()
			return err
		}
	} else {
		v.log.Warn().
			Msg("no Gabriel endpoints provided, starting vehicle without Gabriel")
	}

	// Cleanup goroutine
	go func() {
		// wait for fatal error or context to be canceled
		select {
		case <-ctx.Done():
			v.log.Info().Msg("vehicle context closed, initiating shutdown")
			v.err = ctx.Err()
		}
		v.cleanup()
		// unblock all Vehicle.Wait() calls blocked on this channel
		close(v.shutdown)
	}()

	return nil
}

// Wait blocks until the vehicle hits a fatal error.
func (v *Vehicle) Wait() error {
	if !v.running.Load() {
		return fmt.Errorf("vehicle not running")
	}
	<-v.shutdown
	return v.err
}

func (v *Vehicle) ControlState() string {
	v.policy.mu.RLock()
	defer v.policy.mu.RUnlock()
	return v.policy.currentState
}

// Perform cleanup, releasing any associated system resources.
func (v *Vehicle) cleanup() {
	v.services.GracefulStop()
	v.cancelFn()
	os.RemoveAll(v.RunDir)
	v.running.Store(false)
	v.log.Info().Msg("shutdown complete")
}

func createUnixSocketListener(path string) (net.Listener, error) {
	os.RemoveAll(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("can't listen at file %s: %w", path, err)
	}
	return ln, nil
}
