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
} 

func CreateDriverTestPlugin() (*DriverTestPlugin, error) {

}

func (p *DriverTestPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {

}

func (p *DriverTestPlugin) Stop() error {

}


// Mock mission plugin to act as an endpoint for test clients
struct MissionTestPlugin struct {
    util.BasePlugin
    server  *grpc.Server
    client  *grpc.ClientConn
}

func CreateMissionTestPlugin() (*MissionTestPlugin, error) {

}

func (p *MissionTestPlugin) Spawn(ctx context.Context) (net.Listener, *grpc.ClientConn, error) {

}

func (p *MissionTestPlugin) Stop() error {

}
