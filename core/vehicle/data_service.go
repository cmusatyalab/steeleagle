package vehicle

import (
	"context"

	messages_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages"
	services_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services"
)

type DataService struct {
	services_pb.UnimplementedDataServiceServer
	vehicle          *Vehicle
	latest_telemetry *messages_pb.Telemetry
	latest_frame     *messages_pb.EncodedFrame
}

func (s *DataService) GetResult(ctx context.Context, req *services_pb.GetResultRequest) (*services_pb.GetResultResponse, error) {
	return nil, nil
}

func (s *DataService) GetTelemetry(ctx context.Context, req *services_pb.GetTelemetryRequest) (*services_pb.GetTelemetryResponse, error) {
	return nil, nil
}

func (s *DataService) GetFrame(ctx context.Context, req *services_pb.GetFrameRequest) (*services_pb.GetFrameResponse, error) {
	return nil, nil
}
