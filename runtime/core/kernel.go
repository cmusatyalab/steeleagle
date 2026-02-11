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
    "tailscale.com/tsnet"
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
    port int
    useVPN bool
    wlanConn net.Listener
    localConn net.Listener
}

type Kernel struct {
    // Public
    Name string
    Path string
    // Private
    mu sync.RWMutex
    test bool
    services serviceState
    connections connectionState
    policy policyState
    // Context related attributes
    ctx context.Context
    cancel context.CancelFunc
}

func NewKernel(parentCtx context.Context, options ...KernelOption) (*Kernel, error) {
    // Set up new context
    ctx, cancel := context.WithCancel(parentCtx)

    // Set default input options and retrieve options
    kernel := &Kernel {
        Name : uuid.New().String(),
        ctx : ctx,
        cancel : cancel,
    }
    for _, option := range options {
        option(kernel)
    }
    
    // Create runtime directory if it doesn't exist
    kernel.Path = filepath.Join(xdg.RuntimeDir, ApplicationName, kernel.Name)
    err := os.MkdirAll(kernel.Path, 0755)
    if err != nil {
        slog.Error("could not create runtime directory", "error", err)
        return nil, err
    }
    
    // Set up law handling
    regoPolicy := getRegoPolicy()
    laws, first := getLaw()
    kernel.policy = policyState{
        currentState: first,
        lawMap: laws,
        query: regoPolicy,
        test: kernel.test,
    }
    
    // Create UDS files for the Control and Mission services so that they
    // can be shared with any plugins at start time
    err = os.MkdirAll(filepath.Join(kernel.Path, "control"), os.ModePerm)
    if err != nil {
        slog.Error("could not create control directory", "error", err)
        return nil, err
    }
    kernel.services.control, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(kernel.Path, "control", ControlSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		slog.Error("failed to establish control socket", "error", err)
        return nil, err
	}

    err = os.MkdirAll(filepath.Join(kernel.Path, "mission"), os.ModePerm)
    if err != nil {
        slog.Error("could not create mission directory", "error", err)
        return nil, err
    }
    kernel.services.mission, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(kernel.Path, "mission", MissionSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		slog.Error("failed to establish mission socket", "error", err)
        return nil, err
	}

    // Create 0MQ data sockets
    kernel.services.dataOut = zmq4.NewXSub(ctx)
    err = kernel.services.dataOut.Listen(fmt.Sprintf("ipc://%s", filepath.Join(kernel.Path, DataOutSocket)))
	if err != nil {
        slog.Error("failed to bind data out socket", "error", err)
        return nil, err
	}

	kernel.services.dataIn = zmq4.NewXPub(ctx)
    err = kernel.services.dataIn.Listen(fmt.Sprintf("ipc://%s", filepath.Join(kernel.Path, DataInSocket)))
	if err != nil {
        slog.Error("failed to bind data in socket", "error", err)
        return nil, err
	}
    
    kernel.services.proxy = zmq4.NewProxy(ctx, kernel.services.dataOut, kernel.services.dataIn, nil)

    // Set up gRPC server and set up interceptor chain
    kernel.services.grpcServer = grpc.NewServer(
        grpc.UnaryInterceptor(kernel.policy.getUnaryInterceptor()),
        grpc.StreamInterceptor(kernel.policy.getStreamInterceptor()),
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(
            getProxyDirector(
                kernel.services.control, 
                kernel.services.mission,
            ),
        )),
    )

    go kernel.run()
    return kernel, nil
}

func (i *Kernel) run() {
    // Set up WLAN network listener, if requested
    var err error
    portStr := fmt.Sprintf(":%d", i.connections.port)
    if i.connections.useVPN && i.connections.port != 0 {
        tsSrv := new(tsnet.Server)
        tsSrv.Hostname = i.Name
        err = tsSrv.Start()

        if err != nil {
            slog.Error("can't start tsnet server", "error", err)
        } else {
            slog.Info("listening on VPN network", "address", portStr)
            i.connections.wlanConn, err = tsSrv.Listen("tcp", portStr)
        }
    } else if i.connections.port != 0 {
        if !i.test {
            slog.Warn("listening on open address, this should only be done on a secure network!", "address", portStr)
        }
        i.connections.wlanConn, err = net.Listen("tcp", portStr)
    } else {
        slog.Info("ignoring WLAN connection, using local only mode")
    }
    
    // If there's an error here, don't automatically return; a
    // VPN connection is not needed for kernel operation
    if err != nil {
        slog.Error("can't listen on port", "port", portStr)
        slog.Warn("WLAN connection failure, proceeding in local only mode")
    }

    // However, if a local connection cannot be established, the
    // kernel cannot interact with any local services and thus it
    // should abort
    i.connections.localConn, err = net.Listen("unix", filepath.Join(i.Path, MainSocket))
	if err != nil {
        slog.Error("can't listen at file", "error", filepath.Join(i.Path, MainSocket))
        slog.Error("failed to start main services, aborting!")
        return
	}

    // Serve the WLAN and local server endpoints
    if i.connections.wlanConn != nil {
        go func() {
            e := i.services.grpcServer.Serve(i.connections.wlanConn)
            defer i.connections.wlanConn.Close()
            if e != nil {
                slog.Error("WLAN connection closed unexpectedly", "error", e)
            }
        }()
    }

    go func() {
        e := i.services.grpcServer.Serve(i.connections.localConn)
        defer i.connections.localConn.Close()
        if e != nil {
            slog.Error("local connection closed unexpectedly", "error", e)
        }
    }()

    // Serve the data proxy
    go func() {
        e := i.services.proxy.Run()
        defer i.services.dataOut.Close()
        defer i.services.dataIn.Close()
        if e != nil && !errors.Is(err, context.Canceled) {
            slog.Error("data proxy exited unexpectedly", "error", e)
        }
    }()

    // Wait for context to be cancelled
    <-i.ctx.Done()
    
    // Stop the gRPC server
    i.services.grpcServer.GracefulStop()
}

func (i *Kernel) Stop() {
    i.cancel()
}
