package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"

	data_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/data"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type listenerState struct {
	main    net.Listener
	wan     net.Listener
	admin   net.Listener
	mission net.Listener
	plugins []net.Listener
}

type connectionState struct {
	driver  *grpc.ClientConn
	mission *grpc.ClientConn
}

type Vehicle struct {
	name         string // vehicle id
	path         string // path to vehicle implementation
	pluginConfig PluginConfig
	connCfg      ConnectionConfig
	server       *grpc.Server
	listeners    listenerState
	conns        connectionState
	policyCfg    PolicyConfig
	policy       policyState
}

// Create a new vehicle with the given plugins and options.
func NewVehicle(pluginCfg PluginConfig, options ...VehicleOption) (*Vehicle, error) {
	// Set default input options and retrieve options
	vehicle := &Vehicle{
		name:         uuid.New().String(),
		pluginConfig: pluginCfg,
	}
	for _, option := range options {
		option(vehicle)
	}

	// Configure the vehicle runtime directory
	log.Debug().Str("filepath", vehicle.path).Msg("starting vehicle in runtime directory")

	var err error
	vehicle.path, err = util.GetVehicleDirByName(vehicle.name)
	if err != nil {
		log.Fatal().Str("folder", vehicle.path).Msg("Unable to create vehicle directory")
	}
	log.Debug().Str("folder", vehicle.path).Msg("vehicle folder configured")

	// Set up law handling
	vehicle.policy = getPolicy(vehicle.policyCfg)

	// Set up gRPC servers and set up auth interceptor chain
	vehicle.server = grpc.NewServer(
		grpc.StreamInterceptor(vehicle.policy.getInterceptor()),
		grpc.CustomCodec(proxy.Codec()),
		grpc.UnknownServiceHandler(proxy.TransparentHandler(
			vehicle.getProxyDirector(),
		)),
	)

	// Register data service
	data_pb.RegisterDataServiceServer(vehicle.server, &DataService{vehicle: vehicle})

	return vehicle, nil
}

func createUnixSocketListener(path string) (net.Listener, error) {
	os.RemoveAll(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		log.Error().Err(err).Str("file", path).Msg("could not listen on socket, aborting")
		return nil, fmt.Errorf("can't listen at file %s: %w", path, err)
	}
	return ln, nil
}

func (v *Vehicle) Start(ctx context.Context) error {
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Stop the gRPC server once done
	defer v.server.GracefulStop()

	var err error
	// Create a main socket listener with AuthCode ExternalCode. The main
	// socket is a general endpoint for arbitrary entities to make API calls to
	// the vehicle.
	mainSocketPath := filepath.Join(v.path, MainSocket)
	ln, err := createUnixSocketListener(mainSocketPath)
	if err != nil {
		return err
	}
	defer os.RemoveAll(mainSocketPath)
	v.listeners.main = util.NewCodedListener(ln, util.ExternalCode, nil)

	// Create an admin socket listener with AuthCode AdminCode. The admin
	// socket is intended for use by this process.
	adminSocketPath := filepath.Join(v.path, AdminSocket)
	ln, err = createUnixSocketListener(adminSocketPath)
	if err != nil {
		return err
	}
	defer os.RemoveAll(adminSocketPath)

	// Wrap the passed-in WAN listener with AuthCode Server
	if v.connCfg.Listener != nil {
		v.listeners.wan =
			util.NewCodedListener(v.connCfg.Listener, util.ServerCode, util.GetACL(v.connCfg.AllowedIPs, nil))
	}

	// Start mission/driver plugins, and retrieve associated ClientConn and
	// Listener objects
	_, v.conns.driver, err = v.pluginConfig.driver.Start(ctx)
	if err != nil {
		log.Error().Err(err).Msg("could not start driver plugin, aborting")
		return err
	}
	v.listeners.mission, v.conns.mission, err = v.pluginConfig.mission.Start(ctx)
	if err != nil {
		log.Error().Err(err).Msg("could not start mission plugin, aborting")
		return err
	}

	errCh := make(chan error, len(v.pluginConfig.plugins)+3)

	// Start all plugins
	for _, plugin := range v.pluginConfig.plugins {
		lis, _, err := plugin.Start(ctx)
		if err != nil {
			if err != nil {
				return err
			}
		}
		v.listeners.plugins = append(v.listeners.plugins, lis)

		go func() {
			if err := v.server.Serve(lis); err != nil {
				errCh <- fmt.Errorf("plugin listener: %w", err)
			}
		}()
	}

	// Serve the gRPC server at all listeners
	go func() {
		if err := v.server.Serve(v.listeners.main); err != nil {
			errCh <- fmt.Errorf("main listener: %w", err)
		}
	}()
	go func() {
		// TODO: may want to restart the mission plugin instead of
		// returning with an error here
		if err := v.server.Serve(v.listeners.mission); err != nil {
			errCh <- fmt.Errorf("mission listener: %w", err)
		}
	}()
	if v.listeners.wan != nil {
		go func() {
			if err := v.server.Serve(v.listeners.wan); err != nil {
				errCh <- fmt.Errorf("WAN listener: %w", err)
			}
		}()
	}

	// Wait for the context to be cancelled or an error to be returned
	// from a listener
	select {
	case <-ctx.Done():
		return ctx.Err()
	case err := <-errCh:
		return err
	}
}

// Status methods
func (v *Vehicle) Name() string {
	return v.name
}

func (v *Vehicle) Path() string {
	return v.path
}

func (v *Vehicle) ControlState() string {
	v.policy.mu.RLock()
	defer v.policy.mu.RUnlock()
	return v.policy.currentState
}
