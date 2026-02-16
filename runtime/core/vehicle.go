package core

import (
    "fmt"
    "log/slog"
    "os"
    "path/filepath"
    "net"
    "context"
    "sync"
    "errors"

    "github.com/google/uuid"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    "github.com/mwitkow/grpc-proxy/proxy"
    "github.com/adrg/xdg"
    "github.com/go-zeromq/zmq4"
)

type serviceState struct {
    grpcServer *grpc.Server
    control *grpc.ClientConn
    mission *grpc.ClientConn
    dataIn zmq4.Socket
    dataOut zmq4.Socket
    proxy *zmq4.Proxy
}

type connectionState struct {
    externConns []net.Listener
    localConn net.Listener
}

type Vehicle struct {
    // Public
    Name string
    Path string
    // Private
    mu sync.RWMutex
    test bool
    logLevel *slog.LevelVar
    services serviceState
    connections connectionState
    lawFile string
    policy policyState
    // Context related attributes
    ctx context.Context
    cancel context.CancelFunc
}

var logger *slog.Logger

func NewVehicle(parentCtx context.Context, options ...VehicleOption) (*Vehicle, error) {
    // Set up new context
    ctx, cancel := context.WithCancel(parentCtx)

    // Set default input options and retrieve options
    vehicle := &Vehicle {
        Name : uuid.New().String(),
        logLevel : new(slog.LevelVar),
        ctx : ctx,
        cancel : cancel,
    }
    vehicle.logLevel.Set(slog.LevelInfo)

    for _, option := range options {
        option(vehicle)
    }

    logger = slog.New(
        slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level : vehicle.logLevel}),
    ).With("name", vehicle.Name)
    
    // Create runtime directory if it doesn't exist
    vehicle.Path = filepath.Join(xdg.RuntimeDir, ApplicationName, vehicle.Name)
    err := os.MkdirAll(vehicle.Path, 0755)
    if err != nil {
        logger.Error("could not create runtime directory", "error", err)
        return nil, err
    }
    logger.Debug("vehicle folder configured", "folder", vehicle.Path)
    
    // Set up law handling
    vehicle.policy = getPolicy(vehicle.lawFile)
    
    // Create UDS files for the Control and Mission services so that they
    // can be shared with any plugins at start time
    err = os.MkdirAll(filepath.Join(vehicle.Path, "control"), os.ModePerm)
    if err != nil {
        logger.Error("could not create control directory", "error", err)
        return nil, err
    }
    vehicle.services.control, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(vehicle.Path, "control", ControlSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		logger.Error("failed to establish control socket", "error", err)
        return nil, err
	}

    err = os.MkdirAll(filepath.Join(vehicle.Path, "mission"), os.ModePerm)
    if err != nil {
        logger.Error("could not create mission directory", "error", err)
        return nil, err
    }
    vehicle.services.mission, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(vehicle.Path, "mission", MissionSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		logger.Error("failed to establish mission socket", "error", err)
        return nil, err
	}

    // Create 0MQ data sockets
    vehicle.services.dataOut = zmq4.NewXSub(ctx)
    err = vehicle.services.dataOut.Listen(fmt.Sprintf("ipc://%s", filepath.Join(vehicle.Path, DataOutSocket)))
	if err != nil {
        logger.Error("failed to bind data out socket", "error", err)
        return nil, err
	}

	vehicle.services.dataIn = zmq4.NewXPub(ctx)
    err = vehicle.services.dataIn.Listen(fmt.Sprintf("ipc://%s", filepath.Join(vehicle.Path, DataInSocket)))
	if err != nil {
        logger.Error("failed to bind data in socket", "error", err)
        return nil, err
	}
    
    vehicle.services.proxy = zmq4.NewProxy(ctx, vehicle.services.dataOut, vehicle.services.dataIn, nil)

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
    i.connections.localConn, err = net.Listen("unix", filepath.Join(i.Path, MainSocket))
	if err != nil {
        logger.Error("can't listen at file", "error", filepath.Join(i.Path, MainSocket))
        logger.Error("failed to start main services, aborting!")
        return
	}

    // Serve any attached external listeners
    if len(i.connections.externConns) > 0 {
        for _, conn := range(i.connections.externConns) { 
            go func() {
                e := i.services.grpcServer.Serve(conn)
                defer conn.Close()
                if e != nil {
                    logger.Error("external connection closed unexpectedly", "error", e)
                }
            }()
        }
    }

    go func() {
        e := i.services.grpcServer.Serve(i.connections.localConn)
        defer i.connections.localConn.Close()
        if e != nil {
            logger.Error("local connection closed unexpectedly", "error", e)
        }
    }()

    // Serve the data proxy
    go func() {
        e := i.services.proxy.Run()
        defer i.services.dataOut.Close()
        defer i.services.dataIn.Close()
        if e != nil && !errors.Is(e, context.Canceled) {
            logger.Error("data proxy exited unexpectedly", "error", e)
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
