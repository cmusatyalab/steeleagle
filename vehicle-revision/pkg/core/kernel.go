package core

import (
    "log"
    "log/slog"
    "os"
    "path/filepath"

    "google.golang.org/grpc"
    "tailscale.com/tsnet"
    "github.com/open-policy-agent/opa/rego"
    "github.com/mwitkow/grpc-proxy/proxy"
    "github.com/adrg/xdg"
    "github.com/cmusatyalab/steeleagle/vehicle/pkg/pb"
)

type KernelConfig struct {
    Name string
    Port int
    UseVPN bool
    MissionPackage string
    SandboxMission bool
    DriverPackage string
}

type KernelOption func(*KernelConfig)

func StartKernel(options ...KernelOption) error {
    // Set default input options and retrieve options
    config := &KernelConfig {
        Name : uuid(),
        Port : DefaultPort,
        UseVPN : true,
        SandboxMission : true
    }
    for _, option := range options {
        option(config)
    }

    // Create runtime directory if it doesn't exist
    var runtimePath = filepath.join(RuntimeDirectory, ApplicationName, config.Name)
    err := os.MkdirAll(runtimePath, 0755)
    if err != nil {
        panic(err)
    }
    
    // Create data directory if it doesn't exist, and check for packages

    // Run driver package

    // Run mission package in a sandbox if necessary

    // Establish link to Control and Mission services, if they are requested,
    // then wait for the links to be established
    //links :=

    // Set up VPN or network listener
    var conn net.Listener
    var err error
    portStr := fmt.Sprintf(":%d", config.Port)
    if useVPN {
        tsSrv := new(tsnet.Server)
        tsSrv.Hostname = *config.Name

        if err = tsSrv.Start(); err != nil {
            slog.Error("can't start tsnet server: %v", err)
        }
        defer tsSrv.Close()

        conn, err = tsSrv.Listen("tcp", portStr)
    } else {
        conn, err = net.Listen("tcp", portStr)
    }
    
    if err != nil {
        slog.Error("can't listen on port: %d", config.Port)
    }
    defer conn.Close()

    // Set up law handling
    regoPolicy := getRegoPolicy()
    laws, first  := getLaw()
    policy := policyState{first, sync.Mutex(), laws, regoPolicy}

    // Start gRPC server and set up interceptor chain
    server := grpc.NewServer(
        grpc.CustomCodec(proxy.Codec()),
        grpc.UnknownServiceHandler(proxy.TransparentHandler(proxyDirector))
    )
    //pb.services.compute_service.RegisterComputeServiceServer(server, &computeServiceImpl)
}
