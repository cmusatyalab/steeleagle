package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"slices"
	"time"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

// pluginReadyTimeout bounds how long Start waits for a plugin to report
// healthy over its gRPC connection before aborting vehicle startup.
const pluginReadyTimeout = 15 * time.Second

type Vehicle struct {
	name              string                  // vehicle name
	runDir            string                  // path to vehicle runtime directory
	pluginCfg         PluginConfig            // plugin configuration
	policyCfg         PolicyConfig            // policy configuration
	policy            policyState             // active policy state
	driver            *grpc.ClientConn        // driver gRPC client connection
	mission           *grpc.ClientConn        // mission gRPC client connection
	listeners         map[string]net.Listener // map of names to active listeners
	services          *grpc.Server            // gRPC server instance
	log               zerolog.Logger          // logger object
	errCh             chan error              // error channel shared by listeners
	gabrielClient     gabrielclient.Client    // gabriel remote server client
	videoStreamConfig VideoStreamConfig       // video stream config
	store             *dataStore              // data store
}

// Create a new vehicle with the given plugins and options.
func NewVehicle(
	pluginCfg PluginConfig,
	options ...VehicleOption) (*Vehicle, error) {
	// Set default input options and retrieve options
	vehicle := &Vehicle{
		name:      uuid.New().String(),
		listeners: make(map[string]net.Listener),
		pluginCfg: pluginCfg,
		log:       zerolog.New(os.Stderr).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Create the runtime directory
	var err error
	vehicle.runDir, err = util.GetVehicleDirByName(vehicle.name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("folder", vehicle.runDir).
			Msg("Unable to create vehicle directory")
		return nil, err
	}
	vehicle.log.Debug().Str("folder", vehicle.runDir).
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
	vehicle.store, err = newDataStore(vehicle.name)
	if err != nil {
		return nil, err
	}

	// Register data service
	vehiclepb.RegisterDataServiceServer(
		vehicle.services,
		&DataService{store: vehicle.store})

	return vehicle, nil
}

// Start the vehicle.
func (v *Vehicle) Start(ctx context.Context) error {
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Create a main socket listener with AuthCode ExternalCode. The main
	// socket is a general endpoint for arbitrary entities to make API calls to
	// the vehicle
	var err error
	mainSocketPath := filepath.Join(v.runDir, MainSocketName)
	ln, err := createUnixSocketListener(mainSocketPath)
	if err != nil {
		v.log.Error().Err(err).Str("path", mainSocketPath).
			Msg("failed to create socket listener for main services")
		return err
	}
	v.listeners[MainListenerName] =
		util.NewCodedListener(ln, util.ExternalCode, nil)

	// Create an admin socket listener with AuthCode AdminCode. The admin
	// socket is intended for use by this process
	adminSocketPath := filepath.Join(v.runDir, AdminSocketName)
	ln, err = createUnixSocketListener(adminSocketPath)
	if err != nil {
		v.log.Error().Err(err).Str("path", mainSocketPath).
			Msg("failed to create socket listener for admin services")
		return err
	}
	v.listeners[AdminListenerName] =
		util.NewCodedListener(
			ln,
			util.AdminCode,
			util.GetACL(nil, []int{os.Getpid()}),
		)

	// Start driver plugin
	if v.pluginCfg.Driver == nil {
		v.log.Error().Msg("no driver provided, aborting")
		return fmt.Errorf("no driver provided, aborting")
	}
	_, v.driver, err = v.pluginCfg.Driver.Start(ctx)
	if err != nil {
		v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
		return err
	}
	if err := waitForPluginReady(ctx, v.driver); err != nil {
		v.log.Error().Err(err).
			Msg("driver plugin did not become ready, aborting")
		return err
	}
	v.log.Debug().Msgf("driver plugin %s started!", v.pluginCfg.Driver.Name())

	// Start mission plugin
	if v.pluginCfg.Mission == nil {
		v.log.Debug().Msg("no mission provided, continuing with no mission")
	} else {
		ln, v.mission, err = v.pluginCfg.Mission.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).
				Msg("could not start mission plugin, aborting")
			return err
		}
		if err := waitForPluginReady(ctx, v.mission); err != nil {
			v.log.Error().Err(err).
				Msg("mission plugin did not become ready, aborting")
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
			return err
		}
		if ln != nil && !slices.Contains(ReservedNames, plugin.Name()) && !slices.Contains(ReservedCodes, plugin.Code()) {
			v.listeners[plugin.Name()] = ln
		} else {
			v.log.Debug().
				Msgf("plugin %s listener not added: doesn't exist or has a reserved name/code", plugin.Name())
		}
		v.log.Debug().Msgf("plugin %s started!", plugin.Name())
	}

	// Serve the gRPC server at all listeners
	v.errCh = make(chan error, len(v.listeners))
	for name, ln := range v.listeners {
		go func() {
			if err := v.services.Serve(ln); err != nil {
				v.log.Error().Err(err).Str("listener", name).
					Msg("listener exited with error")
				v.errCh <- fmt.Errorf(
					"listener %s exited with error: %w", name, err,
				)
			}
		}()
	}

	// Start streaming frames and telemetry from the driver
	streamErrCh, err := v.startDriverStreaming(ctx)
	if err != nil {
		v.log.Err(err).Msg("failed to stream from driver")
		return err
	}

	// Initialize the store, launching goroutine to flush telemetry data to
	// disk periodically
	v.store.init(ctx)

	// create gabriel client with telemetry and frame producers
	v.createGabrielClient()
	gabrielErrCh, err := v.gabrielClient.Launch(ctx)
	if err != nil {
		v.log.Err(err).Msg("failed to launch Gabriel client")
		return err
	}

	select {
	case <-ctx.Done():
		return nil
	case err = <-streamErrCh:
		return err
	case err = <-v.errCh:
		return err
	case err = <-gabrielErrCh:
		return err
	}
}

// waitForPluginReady blocks until conn reports healthy or pluginReadyTimeout
// elapses.
func waitForPluginReady(ctx context.Context, conn *grpc.ClientConn) error {
	if conn == nil {
		return nil
	}
	ctx, cancel := context.WithTimeout(ctx, pluginReadyTimeout)
	defer cancel()
	return util.WaitForReady(ctx, conn)
}

func (v *Vehicle) Stop() {
	v.services.GracefulStop()
	os.RemoveAll(v.runDir)
}

func (v *Vehicle) Watch() <-chan error {
	return v.errCh
}

func (v *Vehicle) Name() string {
	return v.name
}

func (v *Vehicle) ControlState() string {
	v.policy.mu.RLock()
	defer v.policy.mu.RUnlock()
	return v.policy.currentState
}

func createUnixSocketListener(path string) (net.Listener, error) {
	os.RemoveAll(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("can't listen at file %s: %w", path, err)
	}
	return ln, nil
}
