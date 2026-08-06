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
func (s *DataService) GetResult(
	ctx context.Context,
	req *vehiclepb.GetResultRequest) (*vehiclepb.GetResultResponse, error) {
	producer_name := req.GetName()
	res := s.store.getLatestResult(producer_name)
	resp := vehiclepb.GetResultResponse_builder{Result: res}.Build()
	return resp, nil
}

// GetTelemetry implements the GetTelemetry RPC defined in data.proto. It
// returns the latest telemetry available for this vehicle.
func (s *DataService) GetTelemetry(
	ctx context.Context,
	req *vehiclepb.GetTelemetryRequest) (*vehiclepb.GetTelemetryResponse, error) {
	tel := s.store.getLatestTelemetry()
	resp := vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build()
	return resp, nil
}

// GetFrame implements the GetFrame RPC defined in data.proto. It returns the
// latest video frame available for this vehicle.
func (s *DataService) GetFrame(
	ctx context.Context,
	req *vehiclepb.GetFrameRequest) (*vehiclepb.GetFrameResponse, error) {
	frame := s.store.getLatestFrame()
	resp := vehiclepb.GetFrameResponse_builder{Frame: frame}.Build()
	return resp, nil
}

// StreamVideoFrames implements the StreamVideoFrames RPC defined in
// data.proto. It returns a stream of video frames from the vehicle.
func (s *DataService) StreamVideoFrames(
	req *vehiclepb.StreamVideoFramesRequest,
	stream vehiclepb.DataService_StreamVideoFramesServer) error {
	ch := s.store.subscribeToFrames()
	for {
		select {
		case <-stream.Context().Done():
			return stream.Context().Err()
		case frame := <-ch:
			resp := vehiclepb.StreamVideoFramesResponse_builder{Frame: frame}.Build()
			stream.Send(resp)
		}
	}
}

// StreamTelemetry implements the StreamTelemetry RPC defined in data.proto. It
// returns a stream of telemetry from the vehicle.
func (s *DataService) StreamTelemetry(
	req *vehiclepb.StreamTelemetryRequest,
	stream vehiclepb.DataService_StreamTelemetryServer) error {
	ch := s.store.subscribeToTelemetry()
	for {
		select {
		case <-stream.Context().Done():
			return stream.Context().Err()
		case tel := <-ch:
			resp := vehiclepb.StreamTelemetryResponse_builder{Telemetry: tel}.Build()
			stream.Send(resp)
		}
	}
}
