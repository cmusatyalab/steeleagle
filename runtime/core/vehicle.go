package core

import (
    "fmt"
    "os"
    "path/filepath"
    "net"
    "context"
    "sync"

    "github.com/google/uuid"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    "github.com/mwitkow/grpc-proxy/proxy"
    "go.nanomsg.org/mangos/v3"
	"go.nanomsg.org/mangos/v3/protocol/xpub"
	"go.nanomsg.org/mangos/v3/protocol/xsub"
    _ "go.nanomsg.org/mangos/v3/transport/all"
    "github.com/adrg/xdg"
    "github.com/rs/zerolog"
)

type serviceState struct {
    grpcServer *grpc.Server
    control *grpc.ClientConn
    mission *grpc.ClientConn
    dataIn mangos.Socket
    dataOut mangos.Socket
}

type connectionState struct {
    externGRPC []net.Listener
    localGRPC net.Listener
}

type Vehicle struct {
    // Public
    Name string
    Path string
    // Private
    mu sync.RWMutex
    test bool
    logLevel string
    services serviceState
    connections connectionState
    policy policyState
    // Filepaths
    logFile string
    lawFile string
    // Context related attributes
    ctx context.Context
    cancel context.CancelFunc
}

var logger zerolog.Logger

func NewVehicle(parentCtx context.Context, options ...VehicleOption) (*Vehicle, error) {
    // Set up new context
    ctx, cancel := context.WithCancel(parentCtx)

    // Set default input options and retrieve options
    vehicle := &Vehicle {
        Name: uuid.New().String(),
        logLevel: "info",
        ctx: ctx,
        cancel: cancel,
    }

    for _, option := range options {
        option(vehicle)
    }

    // Create the logger
    logger = NewChannelLogger(vehicle.logLevel)

    // Create runtime directory if it doesn't exist
    vehicle.Path = filepath.Join(xdg.RuntimeDir, ApplicationName, vehicle.Name)
    logger.Debug().Str("filepath", vehicle.Path).Msg("starting vehicle in runtime directory")
    err := os.MkdirAll(vehicle.Path, 0755)
    if err != nil {
        logger.Error().Err(err).Msg("could not create runtime directory")
        return nil, err
    }
    logger.Debug().Str("folder", vehicle.Path).Msg("vehicle folder configured")
    
    // Set up law handling
    vehicle.policy = getPolicy(vehicle.lawFile)
    
    // Create UDS files for the Control and Mission services so that they
    // can be shared with any plugins at start time
    err = os.MkdirAll(filepath.Join(vehicle.Path, "control"), os.ModePerm)
    if err != nil {
        logger.Error().Err(err).Msg("could not create control directory")
        return nil, err
    }
    vehicle.services.control, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(vehicle.Path, "control", ControlSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		logger.Error().Err(err).Msg("failed to establish control socket")
        return nil, err
	}

    err = os.MkdirAll(filepath.Join(vehicle.Path, "mission"), os.ModePerm)
    if err != nil {
        logger.Error().Err(err).Msg("could not create mission directory")
        return nil, err
    }
    vehicle.services.mission, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(vehicle.Path, "mission", MissionSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		logger.Error().Err(err).Msg("failed to establish mission socket")
        return nil, err
	}

    // Create NNG data proxy
    vehicle.services.dataOut, err = xpub.NewSocket()
    if err != nil {
        logger.Error().Err(err).Msg("failed to create data out socket")
        return nil, err
	}
    err = vehicle.services.dataOut.Listen(fmt.Sprintf("ipc://%s", filepath.Join(vehicle.Path, DataOutSocket)))
	if err != nil {
        logger.Error().Err(err).Msg("failed to bind data out socket")
        return nil, err
	}

	vehicle.services.dataIn, err = xsub.NewSocket()
    if err != nil {
        logger.Error().Err(err).Msg("failed to create data in socket")
        return nil, err
	}
    err = vehicle.services.dataIn.Listen(fmt.Sprintf("ipc://%s", filepath.Join(vehicle.Path, DataInSocket)))
	if err != nil {
        logger.Error().Err(err).Msg("failed to bind data in socket")
        return nil, err
	}

    vehicle.services.dataOut.SetOption(mangos.OptionRaw, true)
    vehicle.services.dataIn.SetOption(mangos.OptionRaw, true)
    
    // Set up gRPC server and set up interceptor chain
    vehicle.services.grpcServer = grpc.NewServer(
        grpc.UnaryInterceptor(vehicle.policy.getUnaryInterceptor(vehicle.test)),
        grpc.StreamInterceptor(vehicle.policy.getStreamInterceptor(vehicle.test)),
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(
            getProxyDirector(
                vehicle.services.control, 
                vehicle.services.mission,
            ),
        )),
    )

    go vehicle.run()
    return vehicle, nil
}

func (i *Vehicle) run() {
    // If a local connection cannot be established, the vehicle cannot
    // interact with any local services and thus it should abort
    var err error
    i.connections.localGRPC, err = net.Listen("unix", filepath.Join(i.Path, MainSocket))
	if err != nil {
        logger.Error().Err(err).Str("file", filepath.Join(i.Path, MainSocket)).Msg("can't listen at file")
        logger.Error().Msg("failed to start main services, aborting!")
        return
	}

    // Serve the data proxy
    err = mangos.Device(i.services.dataIn, i.services.dataOut)
    if err != nil {
        logger.Error().Err(err).Msg("error creating data proxy")  
        return
    }
    defer i.services.dataIn.Close()
    defer i.services.dataOut.Close()

    // Serve any attached external listeners
    if len(i.connections.externGRPC) > 0 {
        for _, conn := range(i.connections.externGRPC) { 
            go func() {
                e := i.services.grpcServer.Serve(conn)
                defer conn.Close()
                if e != nil {
                    logger.Error().Err(err).Msg("external connection closed unexpectedly")
                }
            }()
        }
    }

    go func() {
        e := i.services.grpcServer.Serve(i.connections.localGRPC)
        defer i.connections.localGRPC.Close()
        if e != nil {
            logger.Error().Err(err).Msg("local connection closed unexpectedly")
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
