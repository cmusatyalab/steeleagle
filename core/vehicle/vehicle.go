package vehicle

import (
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
    "github.com/cmusatyalab/steeleagle/core/plugin"
)

type serviceState struct {
    wanSrv       *grpc.Server
    missionSrv   *grpc.Server
    mainSrv      *grpc.Server
    // TODO: add Data and Compute services here, which are vehicle hosted
}

type connectionState struct {
    ipListener   IPListener
    unixListener UnixListener
    // Proxied gRPC connections
    control      *grpc.ClientConn
    stream       *grpc.ClientConn
    mission      *grpc.ClientConn
}

type Vehicle struct {
    name         string
    path         string
    services     serviceState
    connections  connectionState
    plugins      []plugin.Plugin
    // Policy
    policyCfg    PolicyConfig
    policy       policyState
    // Context related attributes
    ctx          context.Context
    cancel       context.CancelFunc
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
    vehicle.services.localServer = grpc.NewServer(
        grpc.StreamInterceptor(vehicle.wlist.getLocalInterceptor()),
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(
            vehicle.getLocalProxyDirector(),
        )),
    )
    
    vehicle.services.externServer = grpc.NewServer(
        grpc.StreamInterceptor(vehicle.wlist.getExternalInterceptor()),
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(
            vehicle.getExternalProxyDirector(),
        )),
    )

    return vehicle, nil
}

func (i *Vehicle) Start() error {
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
                e := i.services.externServer.Serve(conn)
                defer conn.Close()
                if e != nil {
                    log.Error().Err(err).Msg("external connection closed unexpectedly")
                }
            }()
        }
    }

    go func() {
        e := i.services.localServer.Serve(i.connections.localGRPC)
        defer i.connections.localGRPC.Close()
        if e != nil {
            log.Error().Err(err).Msg("local connection closed unexpectedly")
        }
    }()

    // Stop the gRPC servers
    defer i.services.externServer.GracefulStop()
    defer i.services.localServer.GracefulStop()
    
    // Wait for context to be cancelled
    <-i.ctx.Done()
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
