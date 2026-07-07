package vehicle_test

import (
	"context"
	"fmt"
	"io"
	"net"
	"testing"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	mission_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/mission"
	"github.com/cmusatyalab/steeleagle/core/util"
	"google.golang.org/grpc"
)

// ServerSocket is the location of the server listener.
const ServerSocket = "server.sock"

// DriverServerSocket is the location of the driver server.
const DriverServerSocket = "driver-server.sock"

// MissionServerSocket is the location of the mission server.
const MissionServerSocket = "mission-server.sock"

// MissionClientSocket is the location of the mission client listener.
const MissionClientSocket = "mission-client.sock"

// ControlService mocks a ControlService gRPC server.
type ControlService struct {
	driver_pb.UnimplementedControlServiceServer
	commCh chan string
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
	commCh chan string
}

// GetVideoStreamURL mocks and logs a 
func (s *StreamService) GetVideoStreamURL(ctx context.Context, req *driver_pb.GetVideoStreamURLRequest) (*driver_pb.GetVideoStreamURLResponse, error) {
    s.commCh <- "StreamService.GetVideoStreamURL"
    return &driver_pb.GetVideoStreamURLResponse{StreamUrl: s.url}, nil
}

// MissionService mocks a MissionService gRPC server.
type MissionService struct {
	mission_pb.UnimplementedMissionServiceServer
	commCh chan string
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

// setupPlugins creates the mission and driver gRPC servers/plugins for tests. Can
// provide a stream url that the StreamService will respond with as well.
func setupPlugins(t *testing.T, url string) (util.Plugin, util.Plugin, chan string, error) {
	t.Helper()

    // Create command channel
    commCh := make(chan string, 2)

	// Create listeners
	driverLn, err := net.Listen("unix", filepath.Join(t.TempDir(), DriverServerSocket))
	if err != nil {
        return nil, nil, nil, err
	}
	missionLn, err := net.Listen("unix", filepath.Join(t.TempDir(), MissionServerSocket))
	if err != nil {
        return nil, nil, nil, err
	}

	// Server driver and mission services
	driverServer := grpc.NewServer()
	driver_pb.RegisterControlServiceServer(driverServer, &ControlService{commCh: commCh})
    driver_pb.RegisterStreamServiceServer(driverServer, &StreamService{commCh: commCh, url: url})
	missionServer := grpc.NewServer()
	mission_pb.RegisterMissionServiceServer(missionServer, &MissionService{commCh: commCh})
	go driverServer.Serve(driverLn)
	go missionServer.Serve(missionLn)

    // Register cleanup for servers
    t.Cleanup(driverServer.GracefulStop())
    t.Cleanup(missionServer.GracefulStop())

	// Create shim plugins that attach to the pre-created listeners
    driverServer := filepath.Join(t.TempDir(), DriverServerSocket)
	driverPlugin, err := util.CreateShimPlugin(driverServer, "")
	if err != nil {
		return nil, nil, nil, err
	}
    missionServer := filepath.Join(t.TempDir(), MissionServerSocket)
    missionClient := filepath.Join(t.TempDir(), MissionClientSocket)
	missionPlugin, err := util.CreateShimPlugin(missionServer, missionClient)
	if err != nil {
		return nil, nil, nil, err
	}

	return driverPlugin, missionPlugin, commCh, nil
}
