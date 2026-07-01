package vehicle_test

import (
    "net"
    "context"
    "testing"

	"google.golang.org/grpc"
    "github.com/cmusatyalab/steeleagle/core/util"
    driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
    mission_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/mission"
)

// TODO: add removal logic to a main_test.go
// ServerSocket is the location of the server listener.
const ServerSocket = "/tmp/server.sock"
// DriverServerSocket is the location of the driver server.
const DriverServerSocket = "/tmp/driver-server.sock"
// MissionServerSocket is the location of the mission server.
const MissionServerSocket = "/tmp/mission-server.sock"
// MissionClientSocket is the location of the mission client listener.
const MissionClientSocket = "/tmp/mission-client.sock"

// ControlService mocks a ControlService gRPC server.
type ControlService struct {
    driver_pb.UnimplementedControlServiceServer
    commCh  chan string
}

// TakeOff mocks and logs a TakeOff endpoint.
func (c *ControlService) TakeOff(ctx context.Context, req *driver_pb.TakeOffRequest) (*driver_pb.TakeOffResponse, error) {
    c.commCh <- "ControlService.TakeOff"
    return &driver_pb.TakeOffResponse{}, nil
}

// Hold mocks and logs a Hold endpoint.
func (c *ControlService) Hold(ctx context.Context, req *driver_pb.HoldRequest) (*driver_pb.HoldResponse, error) {
    c.commCh <- "ControlService.Hold"
    return &driver_pb.HoldResponse{}, nil
}

// SetVelocity mocks and logs a SetVelocity endpoint.
func (c *ControlService) SetVelocity(ctx context.Context, req *driver_pb.SetVelocityRequest) (*driver_pb.SetVelocityResponse, error) {
    c.commCh <- "ControlService.SetVelocity"
    return &driver_pb.SetVelocityResponse{}, nil
}

// StreamService mocks a StreamService gRPC server.
type StreamService struct {
    driver_pb.UnimplementedStreamServiceServer
    commCh  chan string
}

// TODO: add method implementations here to test streaming

// MissionService mocks a MissionService gRPC server.
type MissionService struct {
   mission_pb.UnimplementedMissionServiceServer
   commCh  chan string
}

// StartMission mocks and logs a StartMission endpoint.
func (m *MissionService) StartMission(ctx context.Context, req *mission_pb.StartMissionRequest) (*mission_pb.StartMissionResponse, error) {
    m.commCh <- "MissionService.StartMission"
    return &mission_pb.StartMissionResponse{}, nil
} 

// StopMission mocks and logs a StopMission endpoint.
func (m *MissionService) StopMission(ctx context.Context, req *mission_pb.StopMissionRequest) (*mission_pb.StopMissionResponse, error) {
    m.commCh <- "MissionService.StopMission"
    return &mission_pb.StopMissionResponse{}, nil
} 

// setupServers creates the mission and driver gRPC servers for tests.
func setupServers(t *testing.T, commCh chan string) (*grpc.Server, *grpc.Server, error) {
    t.Helper()
    // Create listeners
    driverLn, err := net.Listen("unix", DriverServerSocket)
    if err != nil {
        return nil, nil, err
    }
    missionLn, err := net.Listen("unix", MissionServerSocket)
    if err != nil {
        return nil, nil, err
    }

    // Server driver and mission services
    driverServer := grpc.NewServer()
    driver_pb.RegisterControlServiceServer(driverServer, &ControlService{commCh: commCh})
    driver_pb.RegisterStreamServiceServer(driverServer, &StreamService{commCh: commCh})
    missionServer := grpc.NewServer()
    mission_pb.RegisterMissionServiceServer(missionServer, &MissionService{commCh: commCh})
    go driverServer.Serve(driverLn) 
    go missionServer.Serve(missionLn) 
    
    return driverServer, missionServer, nil
}

// setupPlugins sets up the shim plugins for the driver and mission.
func setupPlugins(t *testing.T) (util.Plugin, util.Plugin, error) {
    // Create shim plugins that attach to the pre-created listeners
    driverPlugin, err := util.CreateShimPlugin(DriverServerSocket, "")
    if err != nil {
        return nil, nil, err
    }
    missionPlugin, err := util.CreateShimPlugin(MissionServerSocket, MissionClientSocket)
    if err != nil {
        return nil, nil, err
    }

    return driverPlugin, missionPlugin, nil
}
