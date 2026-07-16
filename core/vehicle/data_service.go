package vehicle

import (
	"context"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
)

// Vehicle gRPC service to get telemetry, frames, and compute results
// associated with this vehicle.
type DataService struct {
	vehiclepb.UnimplementedDataServiceServer
	store *dataStore
}

// GetResult implements the GetResult RPC defined in data.proto. It returns
// the latest compute result available for the specific producer.
func (s *DataService) GetResult(ctx context.Context, req *vehiclepb.GetResultRequest) (*vehiclepb.GetResultResponse, error) {
	producer_name := req.Name
	res := s.store.getLatestResult(producer_name)
	resp := &vehiclepb.GetResultResponse{Result: res}
	return resp, nil
}

// GetTelemetry implements the GetTelemetry RPC defined in data.proto. It
// returns the latest telemetry available for this vehicle.
func (s *DataService) GetTelemetry(ctx context.Context, req *vehiclepb.GetTelemetryRequest) (*vehiclepb.GetTelemetryResponse, error) {
	tel := s.store.getLatestTelemetry()
	resp := &vehiclepb.GetTelemetryResponse{Telemetry: tel}
	return resp, nil
}

// GetFrame implements the GetFrame RPC defined in data.proto. It returns the
// latest video frame available for this vehicle.
func (s *DataService) GetFrame(ctx context.Context, req *vehiclepb.GetFrameRequest) (*vehiclepb.GetFrameResponse, error) {
	frame := s.store.getLatestFrame()
	resp := &vehiclepb.GetFrameResponse{Frame: frame}
	return resp, nil
}
