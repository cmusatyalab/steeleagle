package core

import (
    "fmt"
    "log/slog"
    "os"
    "path/filepath"
    "net"
    "context"

    "github.com/google/uuid"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    "tailscale.com/tsnet"
    "github.com/mwitkow/grpc-proxy/proxy"
    "github.com/adrg/xdg"
    "github.com/go-zeromq/zmq4"
)

type ServiceState struct {
    GRPCServer *grpc.Server
    Control *grpc.ClientConn
    Mission *grpc.ClientConn
    DataIn zmq4.Socket
    DataOut zmq4.Socket
}

type ConnectionState struct {
    Port int
    UseVPN bool
    WLANConn net.Listener
    LocalConn net.Listener
}

type Kernel struct {
    Name string
    Path string
    Plugins []*Plugin
    Connections ConnectionState
    Services ServiceState
    Policy PolicyState
    Test bool
}

type KernelOption func(*Kernel)

func WithName(name string) func(*Kernel) {
    return func(k *Kernel) {
        k.Name = name
    }
}

func WithPort(port int) func(*Kernel) {
    return func(k *Kernel) {
        k.Connections.Port = port
    }
}

func WithVPN(vpn bool) func(*Kernel) {
    return func(k *Kernel) {
        k.Connections.UseVPN = true
    }
}

func WithTest(test bool) func(*Kernel) {
    return func(k *Kernel) {
        k.Test = test
    }
}

func CreateKernel(options ...KernelOption) (*Kernel, error) {
    // Set default input options and retrieve options
    kernel := &Kernel {
        Name : uuid.New().String(),
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
    kernel.Policy = PolicyState{
        State: first,
        Laws: laws,
        Query: regoPolicy,
        test: kernel.Test,
    }
    
    // Create UDS files for the Control and Mission services so that they
    // can be shared with any plugins at start time
    err = os.MkdirAll(filepath.Join(kernel.Path, "control"), os.ModePerm)
    if err != nil {
        slog.Error("could not create control directory", "error", err)
        return nil, err
    }
    kernel.Services.Control, err = grpc.NewClient(
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
    kernel.Services.Mission, err = grpc.NewClient(
        fmt.Sprintf("unix://%s", filepath.Join(kernel.Path, "mission", MissionSocket)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
	if err != nil {
		slog.Error("failed to establish mission socket", "error", err)
        return nil, err
	}

    // Create 0MQ data sockets
    kernel.Services.DataOut = zmq4.NewXSub(context.Background())
    err = kernel.Services.DataOut.Listen(fmt.Sprintf("ipc://%s", filepath.Join(kernel.Path, DataOutSocket)))
	if err != nil {
        slog.Error("failed to bind data out socket", "error", err)
        return nil, err
	}

	kernel.Services.DataIn = zmq4.NewXPub(context.Background())
    err = kernel.Services.DataIn.Listen(fmt.Sprintf("ipc://%s", filepath.Join(kernel.Path, DataInSocket)))
	if err != nil {
        slog.Error("failed to bind data in socket", "error", err)
        return nil, err
	}

    // Set up gRPC server and set up interceptor chain
    kernel.Services.GRPCServer = grpc.NewServer(
        grpc.UnaryInterceptor(kernel.Policy.getUnaryInterceptor()),
        grpc.StreamInterceptor(kernel.Policy.getStreamInterceptor()),
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(
            getProxyDirector(
                kernel.Services.Control, 
                kernel.Services.Mission,
            ),
        )),
    )

    return kernel, nil
}

func (i *Kernel) Start(ctx context.Context) error {
    // Set up WLAN network listener, if requested
    var err error
    portStr := fmt.Sprintf(":%d", i.Connections.Port)
    if i.Connections.UseVPN && i.Connections.Port != 0 {
        tsSrv := new(tsnet.Server)
        tsSrv.Hostname = i.Name
        err = tsSrv.Start()

        if err != nil {
            slog.Error("can't start tsnet server", "error", err)
        } else {
            slog.Info("listening on VPN network", "address", portStr)
            i.Connections.WLANConn, err = tsSrv.Listen("tcp", portStr)
        }
    } else if i.Connections.Port != 0 {
        if !i.Test {
            slog.Warn("listening on open address, this should only be done on a secure network!", "address", portStr)
        }
        i.Connections.WLANConn, err = net.Listen("tcp", portStr)
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
    i.Connections.LocalConn, err = net.Listen("unix", filepath.Join(i.Path, MainSocket))
	if err != nil {
        slog.Error("can't listen at file", "error", filepath.Join(i.Path, MainSocket))
        slog.Error("failed to start main services, aborting!")
        return err
	}

    // Serve the WLAN and local server endpoints
    if i.Connections.WLANConn != nil {
        go func() {
            e := i.Services.GRPCServer.Serve(i.Connections.WLANConn)
            defer i.Connections.WLANConn.Close()
            if e != nil {
                slog.Error("WLAN connection closed unexpectedly", "error", e)
            }
        }()
    }

    go func() {
        e := i.Services.GRPCServer.Serve(i.Connections.LocalConn)
        defer i.Connections.LocalConn.Close()
        if e != nil {
            slog.Error("local connection closed unexpectedly", "error", e)
        }
    }()

    // Serve the data proxy
    go func() {
        pxy := zmq4.NewProxy(ctx, i.Services.DataOut, i.Services.DataIn, nil)
        e := pxy.Run()
        defer i.Services.DataOut.Close()
        defer i.Services.DataIn.Close()
        if e != nil {
            slog.Error("data proxy exited unexpectedly", "error", e)
        }
    }()

    // Wait for context to be cancelled
    <-ctx.Done()
    
    // Stop the gRPC server
    i.Services.GRPCServer.GracefulStop()
    
    return nil
}

func (i *Kernel) AddPlugin(options ...PluginOption) error {
    return nil
}
