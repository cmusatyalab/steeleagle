package vehicle_test

import (
    "context"
    "testing"

    driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
    mission_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/mission"
)

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

func setupServers(t *testing.T) {
    t.Helper()
    // TODO
}
