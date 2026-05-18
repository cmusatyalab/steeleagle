package vehicle_test

import (
    "net"
    "context"

    "github.com/cmusatyalab/steeleagle/core/util"
    services_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services"
	"google.golang.org/grpc"
)

// Mock driver plugin to act as an endpoint for test clients
struct DriverTestPlugin struct {
    util.BasePlugin
    server  *grpc.Server
    channel chan CallType 
} 

func CreateDriverTestPlugin() (*DriverTestPlugin, error) {
    s := grpc.NewServer()
    services_pb.RegisterControlServiceServer(s, &ControlTestService{})
    return &DriverTestPlugin{
        server: grpc.NewServer(),
    }
}

func (p *DriverTestPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
    lnFile, clientFile, err := util.CreateSocketPairFiles()
    if err != nil {
        return err
    }
    ln, client, err := util.CreateEndpoints(lnFile, clientFile)
    if err != nil {
        return err
    }

    go func() {
        if err := p.server.Serve(ln); err != nil {
            return err
        }
    }()

    return nil
}

func (p *DriverTestPlugin) Stop() error {
    p.server.GracefulStop()
}

// Mock mission plugin to act as an endpoint for test clients
struct MissionTestPlugin struct {
    util.BasePlugin
    server  *grpc.Server
    client  *grpc.ClientConn
    channel chan CallType 
}

func CreateMissionTestPlugin() (*MissionTestPlugin, error) {
    s := grpc.NewServer()
    services_pb.RegisterControlServiceServer(s, &MissionTestService{})
    return &MissionTestPlugin{
        server: s,
    }
}

func (p *MissionTestPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {
    lnFile, clientFile, err := util.CreateSocketPairFiles()
    if err != nil {
        return err
    }
    ln, client, err := util.CreateEndpoints(lnFile, clientFile)
    if err != nil {
        return err
    }
    p.client = client

    go func() {
        if err := p.server.Serve(ln); err != nil {
            return err
        }
    }()

    return nil
}

func (p *MissionTestPlugin) Stop() error {
    p.server.GracefulStop()
}

// Service definitions
