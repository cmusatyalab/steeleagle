package vehicle

import (
	"context"

	pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services"
)

type DataService struct {
	pb.UnimplementedDataServiceServer
	vehicle *Vehicle
}

func (s *DataService) GetResult(ctx context.Context, req *pb.GetResultRequest) (*pb.GetResultResponse, error) {
	return nil, nil
}

func (s *DataService) GetTelemetry(ctx context.Context, req *pb.GetTelemetryRequest) (*pb.GetTelemetryResponse, error) {
	return nil, nil
}

func (s *DataService) GetFrame(ctx context.Context, req *pb.GetFrameRequest) (*pb.GetFrameResponse, error) {
	return nil, nil
}
