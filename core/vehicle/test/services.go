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
    GetVideoURL
    GetTelemetryStream
    Error
)

type ControlTestService struct {
    services_pb.UnimplementedControlServiceServer
    channel chan CallType
}

type StreamTestService struct {
    services_pb.UnimplementedStreamServiceServer
    channel chan CallType
}

type MissionTestService struct {
    services_pb.UnimplementedMissionServiceServer
    channel chan CallType
}

func (s *ControlTestService) TakeOff(ctx context.Context, request *services_pb.TakeOffRequest) (*services_pb.TakeOffResponse, error) {
    s.channel <- TakeOff
    return &services_pb.TakeOffResponse{}, nil
}

func (s *ControlTestService) Hold(ctx context.Context, request *services_pb.HoldRequest) (*services_pb.HoldResponse, error) {
    s.channel <- Hold
    return &services_pb.HoldResponse{}, nil
}

func (s *StreamTestService) GetVideoURL(ctx context.Context, request *services_pb.GetVideoURLRequest) (*services_pb.GetVideoURLResponse, error) {
    s.channel <- GetVideoURL
    return &services_pb.GetVideoURLResponse{}, nil
}

func (s *StreamTestService) GetTelemetryStream(request *services_pb.GetTelemetryStreamRequest, srv pb.StreamService_GetTelemetryStreamServer) error {
    s.channel <- GetTelemetryStream
    for i = 0; i < 5; i++ {
        if err = srv.Send(&services_pb.GetTelemetryStreamResponse{}); err != nil {
            s.channel <- Error
            return err
        }
    }
}

func (s *MissionTestService) StartMission(ctx context.Context, request *services_pb.StartMissionRequest) (*services_pb.StartMissionResponse, error) {
    s.channel <- StartMission
    return &services_pb.StartMissionResponse{}, nil
}
