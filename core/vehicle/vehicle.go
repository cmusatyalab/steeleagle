package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"

	vehicle_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type Vehicle struct {
	id           string                  // auto-generated ID for path disambiguation
	name         string                  // vehicle name
	runDir       string                  // path to vehicle runtime directory
	pluginCfg    PluginConfig            // plugin configuration
	policyCfg    PolicyConfig            // policy configuration
	policy       policyState             // active policy state
	driver       *grpc.ClientConn        // driver gRPC client connection
	mission      *grpc.ClientConn        // mission gRPC client connection
	listeners    map[string]net.Listener // map of names to active listeners
	services     *grpc.Server            // gRPC server instance
	log          zerolog.Logger          // logger object
	errCh        chan error              // error channel shared by listeners
}

// Create a new vehicle with the given plugins and options.
func NewVehicle(pluginCfg PluginConfig, options ...VehicleOption) (*Vehicle, error) {
	// Set default input options and retrieve options
	vehicle := &Vehicle{
		id:           uuid.New().String(),
		name:         uuid.New().String(),
		listeners:    make(map[string]net.Listener),
		pluginCfg:    pluginCfg,
		log:          zerolog.New(os.Stdout).With().Timestamp().Logger(),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Create the runtime directory
	var err error
	vehicle.runDir, err = util.GetVehicleDirByID(vehicle.name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("folder", vehicle.runDir).Msg("Unable to create vehicle directory")
		return nil, err
	}
	vehicle.log.Debug().Str("folder", vehicle.runDir).Msg("vehicle folder configured")

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

	// Register data service
	vehicle_pb.RegisterDataServiceServer(vehicle.services, &DataService{})

	return vehicle, nil
}

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
		v.log.Error().Err(err).Str("path", mainSocketPath).Msg("failed to create socket listener for main services")
		return err
	}
	v.listeners[MainListenerName] = util.NewCodedListener(ln, util.ExternalCode, nil)

	// Create an admin socket listener with AuthCode AdminCode. The admin
	// socket is intended for use by this process
	adminSocketPath := filepath.Join(v.runDir, AdminSocketName)
	ln, err = createUnixSocketListener(adminSocketPath)
	if err != nil {
		v.log.Error().Err(err).Str("path", mainSocketPath).Msg("failed to create socket listener for admin services")
		return err
	}
	v.listeners[AdminListenerName] = util.NewCodedListener(ln, util.AdminCode, util.GetACL(nil, []int{os.Getpid()}))

	// Start all plugins and register listeners
	if v.driver != nil {
		_, v.driver, err = v.pluginCfg.Driver.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
			return err
		}
		v.log.Debug().Msgf("driver plugin %s started!", v.pluginCfg.Driver.Name())
	} else {
		v.log.Error().Msg("no driver provided, aborting")
		return fmt.Errorf("no driver provided, aborting")
	}
	if v.pluginCfg.Mission != nil {
		ln, v.mission, err = v.pluginCfg.Mission.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).Msg("could not start mission plugin, aborting")
			return err
		}
		// For logging purposes, use a mission tag instead of the name to disambiguate
		// between this plugin and external plugins
		v.listeners[MissionListenerName] = ln
		v.log.Debug().Msgf("mission plugin %s started!", v.pluginCfg.Mission.Name())
	}
	for _, plugin := range v.pluginCfg.Plugins {
		ln, _, err = plugin.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).Msgf("could not start plugin %s, aborting", plugin.Name())
			return err
		}
        if ln != nil {
		    v.listeners[plugin.Name()] = ln
        }
		v.log.Debug().Msgf("plugin %s started!", plugin.Name())
	}

	// Serve the gRPC server at all listeners
	v.errCh = make(chan error, len(v.listeners))
	for name, ln := range v.listeners {
		go func() {
			if err := v.services.Serve(ln); err != nil {
				v.log.Error().Err(err).Str("listener", name).Msg("listener exited with error")
				v.errCh <- fmt.Errorf("listener %s exited with error: %w", name, err)
			}
		}()
	}

	return nil
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
