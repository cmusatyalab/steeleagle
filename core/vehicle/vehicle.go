package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"syscall"

	"github.com/adrg/xdg"
	services_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type listenerState struct {
	mainLn    net.Listener
	adminLn   net.Listener
	wanLn     net.Listener
	missionLn net.Listener
}

type connectionState struct {
	// Admin gRPC connections
	admin *grpc.ClientConn
	// Proxied gRPC connections
	driver  *grpc.ClientConn
	mission *grpc.ClientConn
}

type Vehicle struct {
	name       string
	path       string
	socketPath string // path to main services socket
	// Plugins
	driver  util.Plugin
	mission util.Plugin
	// Connections
	connCfg   ConnectionConfig
	server    *grpc.Server
	listeners listenerState
	conns     connectionState
	// Policy
	policyCfg PolicyConfig
	policy    policyState
	test      bool
	backend   string
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

	// Register data service
	services_pb.RegisterDataServiceServer(vehicle.server, &DataService{vehicle: vehicle})

	return vehicle, nil
}

func (v *Vehicle) Start(ctx context.Context) error {
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Stop the gRPC server once done
	defer v.server.GracefulStop()

	// Create a socket pair for admin-only connections to the main server
	adminFds, _ := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	adminEndpoint := os.NewFile(uintptr(adminFds[0]), "admin-endpoint")
	adminProxy := os.NewFile(uintptr(adminFds[1]), "admin-proxy")

	var err error
	// Create a main socket listener with AuthCode External
	mainSocket := filepath.Join(v.path, MainSocket)
	ln, err := net.Listen("unix", mainSocket)
	v.listeners.mainLn =
		util.NewListener(ln, util.ExternalCode, nil)
	if err != nil {
		log.Error().Err(err).Str("file", mainSocket).Msg("could not listen on main socket, aborting")
		return fmt.Errorf("can't listen at file %s: %w", mainSocket, err)
	}
	// Create a socket pair listener with AuthCode Admin
	c, err := net.FileConn(adminEndpoint)
	v.listeners.adminLn =
		util.NewSocketPairListener(c, util.AdminCode)
	adminEndpoint.Close() // close the file since we don't need it anymore
	if err != nil {
		log.Error().Err(err).Str("file", "admin-endpoint").Msg("could not listen on admin socket, aborting")
		return fmt.Errorf("can't listen at file %s: %w", "admin-endpoint", err)
	}
	// Wrap the passed-in WAN listener with AuthCode Server
	if v.connCfg.Listener != nil {
		v.listeners.wanLn =
			util.NewListener(v.connCfg.Listener, util.ServerCode, util.GetACL(v.connCfg.AllowedIPs))
		if err != nil {
			log.Error().Err(err).Msg("could not listen on WAN endpoint, aborting")
			return fmt.Errorf("can't listen at WAN endpoint: %w", err)
		}
	}

	// Create admin connection, so internal RPC methods can be
	// authorized with Admin codes
	c, err = net.FileConn(adminProxy)
	v.conns.admin, err = util.NewSocketPairClient(c)
	if err != nil {
		log.Error().Err(err).Str("file", "admin-proxy").Msg("could not set up admin client")
		return fmt.Errorf("can't create client at file %s: %w", "admin-proxy", err)
	}

	// Start mission/driver plugins, and retrieve associated ClientConn and
	// Listener objects
	err = v.driver.Start(ctx)
	if err != nil {
		log.Error().Err(err).Msg("could not start driver plugin, aborting")
	}
	//v.conns.driverPxy = driverconn
	err = v.mission.Start(ctx)
	if err != nil {
		log.Error().Err(err).Msg("could not start mission plugin, aborting")
	}
	//v.listeners.missionLn = missionLn
	//v.conns.mission = missionConn

	// Serve the gRPC server at all listeners
	errCh := make(chan error, 4)
	go func() {
		if err := v.server.Serve(v.listeners.mainLn); err != nil {
			errCh <- fmt.Errorf("main listener: %w", err)
		}
	}()
	go func() {
		if err := v.server.Serve(v.listeners.adminLn); err != nil {
			errCh <- fmt.Errorf("admin listener: %w", err)
		}
	}()
	go func() {
		if err := v.server.Serve(v.listeners.wanLn); err != nil {
			errCh <- fmt.Errorf("WAN listener: %w", err)
		}
	}()
	go func() {
		// TODO: may want to restart the mission plugin instead of
		// returning with an error here
		if err := v.server.Serve(v.listeners.missionLn); err != nil {
			errCh <- fmt.Errorf("mission listener: %w", err)
		}
	}()

	// Wait for the context to be cancelled or an error to be returned
	// from a listener
	select {
	case <-ctx.Done():
		return ctx.Err()
	case err := <-errCh:
		return err
	}
}

func (v *Vehicle) CreatePlugins() error {
	var err error
	v.driver, err = util.CreateProcessPlugin("a", "b")
	if err != nil {
		return err
	}

	v.mission, err = util.CreateProcessPlugin("a", "b")
	if err != nil {
		return err
	}
	return nil
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
