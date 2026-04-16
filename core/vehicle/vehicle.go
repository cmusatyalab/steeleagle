package vehicle

import (
    "fmt"
    "os"
    "path/filepath"
    "net"
    "context"

    "github.com/google/uuid"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    "github.com/mwitkow/grpc-proxy/proxy"
    "github.com/adrg/xdg"
    "github.com/rs/zerolog/log"
)

type serviceState struct {
    extServer  *grpc.Server
    intServer  *grpc.Server
    driver     *grpc.ClientConn
    mission     *grpc.ClientConn
}

type connectionState struct {
    externGRPC  []net.Listener
    localGRPC   net.Listener
}

type Vehicle struct {
    name        string
    path        string
    test        bool
    services    serviceState
    connections connectionState
    // Plugins
    driver      Plugin
    mission     Plugin
    plugins     []Plugin
    // Policy
    policyCfg   PolicyConfig
    policy      policyState
    // Context related attributes
    ctx         context.Context
    cancel      context.CancelFunc
}

func NewVehicle(parentCtx context.Context, options ...VehicleOption) (*Vehicle, error) {
    // Set up new context
    ctx, cancel := context.WithCancel(parentCtx)

    // Set default input options and retrieve options
    vehicle := &Vehicle {
        name: uuid.New().String(),
        ctx: ctx,
        cancel: cancel,
    }

    for _, option := range options {
        option(vehicle)
    }

    // Create runtime directory if it doesn't exist
    vehicle.path = filepath.Join(xdg.RuntimeDir, ApplicationName, vehicle.name)
    log.Debug().Str("filepath", vehicle.path).Msg("starting vehicle in runtime directory")
    err := os.MkdirAll(vehicle.path, 0755)
    if err != nil {
        log.Error().Err(err).Msg("could not create runtime directory")
        return nil, err
    }
    log.Debug().Str("folder", vehicle.path).Msg("vehicle folder configured")

    // Set up law handling
    vehicle.policy = getPolicy(vehicle.policyCfg)
    
    // Set up gRPC server and set up interceptor chain
    vehicle.services.grpcServer = grpc.NewServer(
        grpc.StreamInterceptor(vehicle.policy.getStreamInterceptor(vehicle.test)),
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(
            vehicle.getProxyDirector(),
        )),
    )

    go vehicle.run()
    return vehicle, nil
}

func (i *Vehicle) run() {
    // If a local connection cannot be established, the vehicle cannot
    // interact with any local services and thus it should abort
    var err error
    i.connections.localGRPC, err = net.Listen("unix", filepath.Join(i.path, MainSocket))
	if err != nil {
        log.Error().Err(err).Str("file", filepath.Join(i.path, MainSocket)).Msg("can't listen at file")
        log.Error().Msg("failed to start main services, aborting!")
        return
	}

    // Serve any attached external listeners
    if len(i.connections.externGRPC) > 0 {
        for _, conn := range(i.connections.externGRPC) { 
            go func() {
                e := i.services.grpcServer.Serve(conn)
                defer conn.Close()
                if e != nil {
                    log.Error().Err(err).Msg("external connection closed unexpectedly")
                }
            }()
        }
    }

    go func() {
        e := i.services.grpcServer.Serve(i.connections.localGRPC)
        defer i.connections.localGRPC.Close()
        if e != nil {
            log.Error().Err(err).Msg("local connection closed unexpectedly")
        }
    }()

    // Wait for context to be cancelled
    <-i.ctx.Done()
    
    // Stop the gRPC server
    i.services.grpcServer.GracefulStop()
}

func (i *Vehicle) Stop() {
    i.cancel()
}

// Status methods
func (i *Vehicle) Name() string {
    return i.name
}

func (i *Vehicle) Path() string {
    return i.path
}

func (i *Vehicle) ControlState() string {
    i.policy.mu.RLock()
    defer i.policy.mu.RUnlock()
    return i.policy.currentState
}
