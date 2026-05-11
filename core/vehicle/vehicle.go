package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
    "syscall"

	"github.com/adrg/xdg"
	"github.com/cmusatyalab/steeleagle/core/plugin"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	services_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services"
)

type listenerState struct {
	mainLn      net.Listener
    missionLn   net.Listener
    localLn     net.Listener
	wanLn       net.Listener
}

type connectionState struct {
    // Admin gRPC connections
	control     *grpc.ClientConn
	mission     *grpc.ClientConn
	data        *grpc.ClientConn
    compute     *grpc.ClientConn
	// Proxied gRPC connections
	controlPxy  *grpc.ClientConn
	streamPxy   *grpc.ClientConn
	missionPxy  *grpc.ClientConn
}

type Vehicle struct {
	name        string
	path        string
	socketPath  string // path to main services socket
    // Plugins
	driver      plugin.Plugin
	mission     plugin.Plugin
    // Connections
    connCfg     ConnectionConfig
	server      *grpc.Server
	listeners   listenerState
    conns       connectionState
	// Policy
	policyCfg   PolicyConfig
	policy      policyState
	test        bool
	backend     string
}

func NewVehicle(options ...VehicleOption) (*Vehicle, error) {
	// Set default input options and retrieve options
	vehicle := &Vehicle{
		name: uuid.New().String(),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Configure the vehicle runtime directory
	if vehicle.path == "" {
		vehicle.path = filepath.Join(xdg.RuntimeDir, vehicle.name)
	}
	log.Debug().Str("filepath", vehicle.path).Msg("starting vehicle in runtime directory")
	err := os.MkdirAll(vehicle.path, 0755)
	if err != nil {
		log.Error().Err(err).Msg("could not create runtime directory")
		return nil, err
	}
	log.Debug().Str("folder", vehicle.path).Msg("vehicle folder configured")

	// Configure the main socket for vehicle services, if not specified
	if vehicle.socketPath == "" {
		vehicle.socketPath = filepath.Join(vehicle.path, MainSocket)
		log.Debug().Str("filepath", vehicle.socketPath).Msg("setting main services filepath")
	}

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
    services_pb.RegisterDataServiceServer(vehicle.server, &DataService{vehicle: vehicle})

	return vehicle, nil
}

func (v *Vehicle) Start(ctx context.Context) error {
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

    // Stop the gRPC server once done
    defer v.server.GracefulStop()

    // Create a socket pair for local-only connections to the main server
    localFds, _ := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
    localEndpoint := os.NewFile(uintptr(localFds[0]), "local-endpoint")
    localProxy := os.NewFile(uintptr(localFds[1]), "local-proxy")

	var err error
    // Create a main socket listener with AuthCode External
    mainSocket = filepath.Join(v.path, MainSocket)
	v.connections.mainLn, err =
		NewListener(net.Listen("unix", mainSocket), External, nil)
	if err != nil {
        log.Error().Err(err).Str("file", mainSocket).Msg("could not listen on main socket, aborting")
		return fmt.Errorf("can't listen at file %s: %w", mainSocket, err)
	}
    // Create a socket pair listener with AuthCode Mission
    v.connections.missionLn, err = 
        NewSocketPairListener(net.FileConn(missionEndpoint), Mission, nil)
    missionEndpoint.Close()
	if err != nil {
        log.Error().Err(err).Str("file", "mission-endpoint").Msg("could not listen on mission socket, aborting")
		return fmt.Errorf("can't listen at file %s: %w", "mission-endpoint", err)
	}
    // Create a socket pair listener with AuthCode Admin
    v.connections.localLn, err = 
        NewSocketPairListener(net.FileConn(localEndpoint), Admin, nil)
    localEndpoint.Close()
	if err != nil {
        log.Error().Err(err).Str("file", "local-endpoint").Msg("could not listen on admin socket, aborting")
		return fmt.Errorf("can't listen at file %s: %w", "local-endpoint", err)
	}
    // Wrap the passed-in WAN listener with AuthCode Server
    if v.connCfg.Listener != nil {
        v.connections.wanLn, err = 
            NewListener(v.connCfg.listener, Server, util.GetACL(v.connCfg.AllowedIPs))
	    if err != nil {
            log.Error().Err(err).Msg("could not listen on WAN endpoint, aborting")
	    	return fmt.Errorf("can't listen at WAN endpoint: %w", err)
	    }
    }

	errCh := make(chan error, 3)
	go func() {
		if err := v.services.wanSrv.Serve(v.connections.wanLn); err != nil {
			errCh <- fmt.Errorf("wanSrv: %w", err)
		}
	}()

	go func() {
		if err := v.services.mainSrv.Serve(v.connections.mainLn); err != nil {
			errCh <- fmt.Errorf("mainSrv: %w", err)
		}
	}()

	go func() {
		if err := v.services.dataSrv.Serve(v.connections.mainLn); err != nil {
			errCh <- fmt.Errorf("dataSrv: %w", err)
		}
	}()

	// Wait for the context to be cancelled or an error to be returned from a
	// server
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
