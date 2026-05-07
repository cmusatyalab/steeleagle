package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"

	"github.com/adrg/xdg"
	"github.com/cmusatyalab/steeleagle/core/plugin"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type serviceState struct {
	wanSrv  *grpc.Server
	mainSrv *grpc.Server
	// TODO: add Data and Compute services here, which are vehicle hosted
}

type connectionState struct {
	wanLn  net.Listener
	mainLn net.Listener
	// Proxied gRPC connections
	control    *grpc.ClientConn
	stream     *grpc.ClientConn
	mission    *grpc.ClientConn
	externGRPC []net.Listener
}

type Vehicle struct {
	name        string
	path        string
	spath       string
	services    serviceState
	connections connectionState
	driver      plugin.Plugin
	mission     plugin.Plugin
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
		vehicle.path = filepath.Join(xdg.RuntimeDir, ApplicationName, vehicle.name)
	}
	log.Debug().Str("filepath", vehicle.path).Msg("starting vehicle in runtime directory")
	err := os.MkdirAll(vehicle.path, 0755)
	if err != nil {
		log.Error().Err(err).Msg("could not create runtime directory")
		return nil, err
	}
	log.Debug().Str("folder", vehicle.path).Msg("vehicle folder configured")

	// Configure the main socket for vehicle services, if not specified
	if vehicle.spath == "" {
		vehicle.spath = filepath.Join(vehicle.path, MainSocket)
		log.Debug().Str("filepath", vehicle.spath).Msg("setting main services filepath")
	}

	// Set up law handling
	vehicle.policy = getPolicy(vehicle.policyCfg)

	// Build the authenticator PID lookup table, add own PID
	// TODO: whitelist other PIDs

	// Create a new credential service that assigns auth codes

	// Pass these to the corresponding servers

	// Set up gRPC servers and set up auth interceptor chain
	vehicle.services.wanSrv = grpc.NewServer(
		grpc.StreamInterceptor(vehicle.wlist.getExternalInterceptor()),
		grpc.CustomCodec(proxy.Codec()),
		grpc.UnknownServiceHandler(proxy.TransparentHandler(
			vehicle.getExternalProxyDirector(),
		)),
	)

	vehicle.services.mainSrv = grpc.NewServer(
		grpc.StreamInterceptor(vehicle.wlist.getExternalInterceptor()),
		grpc.CustomCodec(proxy.Codec()),
		grpc.UnknownServiceHandler(proxy.TransparentHandler(
			vehicle.getExternalProxyDirector(),
		)),
	)

	return vehicle, nil
}

func (v *Vehicle) Start(ctx context.Context) error {
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// If a local connection cannot be established, the vehicle cannot
	// interact with any local services and thus it should abort
	var err error
	v.connections.mainLn, err =
		net.Listen("unix", filepath.Join(v.path, MainSocket))
	if err != nil {
		return fmt.Errorf(
			"can't listen at file %s: %w",
			filepath.Join(v.path, MainSocket),
			err,
		)
	}

	// Stop the gRPC servers
	defer v.services.wanSrv.GracefulStop()
	defer v.services.mainSrv.GracefulStop()

	errCh := make(chan error, 2)
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
