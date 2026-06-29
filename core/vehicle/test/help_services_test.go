package vehicle_test

import (
	"context"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	mission_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/mission"
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
	driver_pb.UnimplementedControlServiceServer
	channel chan CallType
}

type StreamTestService struct {
	driver_pb.UnimplementedStreamServiceServer
	channel chan CallType
}

type MissionTestService struct {
	mission_pb.UnimplementedMissionServiceServer
	channel chan CallType
}

func (s *ControlTestService) TakeOff(ctx context.Context, request *driver_pb.TakeOffRequest) (*driver_pb.TakeOffResponse, error) {
	s.channel <- TakeOff
	return &driver_pb.TakeOffResponse{}, nil
}

func (s *ControlTestService) Hold(ctx context.Context, request *driver_pb.HoldRequest) (*driver_pb.HoldResponse, error) {
	s.channel <- Hold
	return &driver_pb.HoldResponse{}, nil
}

func (s *StreamTestService) GetVideoURL(ctx context.Context, request *driver_pb.GetVideoStreamURLRequest) (*driver_pb.GetVideoStreamURLResponse, error) {
	s.channel <- GetVideoURL
	return &driver_pb.GetVideoStreamURLResponse{}, nil
}

func (s *StreamTestService) GetTelemetryStream(request *driver_pb.StreamTelemetryRequest, srv driver_pb.StreamService_StreamTelemetryServer) error {
	s.channel <- GetTelemetryStream
	for i := 0; i < 5; i++ {
		if err := srv.Send(&driver_pb.StreamTelemetryResponse{}); err != nil {
			s.channel <- Error
			return err
		}
	}
	return nil
}

func (s *MissionTestService) StartMission(ctx context.Context, request *mission_pb.StartMissionRequest) (*mission_pb.StartMissionResponse, error) {
	s.channel <- StartMission
	return &mission_pb.StartMissionResponse{}, nil
}
