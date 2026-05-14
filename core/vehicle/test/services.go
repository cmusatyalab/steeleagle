package vehicle_test

import (
	"context"

	services_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services"
)

type CallType int

const (
    TakeOff CallType = iota
    Hold
    StartMission
)

type ControlService struct {
    services_pb.UnimplementedControlServiceServer
    channel chan CallType
}

type MissionService struct {
    services_pb.UnimplementedMissionServiceServer
    channel chan CallType
}

func (s *ControlService) TakeOff(ctx context.Context, request *services_pb.TakeOffRequest) (*services_pb.TakeOffResponse, error) {
    s.channel <- TakeOff
    return &services_pb.TakeOffRequest{}, nil
}

func (s *ControlService) Hold(ctx context.Context, request *services_pb.HoldRequest) (*services_pb.HoldResponse, error) {
    s.channel <- Hold
    return &services_pb.HoldRequest{}, nil
}

func (s *MissionService) StartMission(ctx context.Context, request *services_pb.StartMissionRequest) (*services_pb.StartMissionResponse, error) {
    s.channel <- StartMission
    return &services_pb.StartMissionRequest{}, nil
}
