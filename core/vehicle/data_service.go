package vehicle

import (
	"context"
	"fmt"
	"io"
	"sync"

	result_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/result"
	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	vehicle_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/vehicle"
	"google.golang.org/grpc"
)

type DataService struct {
	vehicle_pb.UnimplementedDataServiceServer
	vehicle          *Vehicle
	latest_telemetry *stream_msg_pb.Telemetry
	latest_frame     *stream_msg_pb.EncodedFrame
	latest_results   map[string]*result_pb.ComputeResult
	tel_mu           *sync.RWMutex
	frame_mu         *sync.RWMutex
	result_mu        *sync.RWMutex
}

func (s *DataService) GetResult(ctx context.Context, req *vehicle_pb.GetResultRequest) (*vehicle_pb.GetResultResponse, error) {
	s.result_mu.RLock()
	defer s.result_mu.RUnlock()
	producer_name := req.Name
	var val *result_pb.ComputeResult
	var ok bool
	if val, ok = s.latest_results[producer_name]; !ok {
		return nil, fmt.Errorf("producer %s not found", producer_name)
	}
	if val == nil {
		return nil, fmt.Errorf("no result available for producer %s", producer_name)
	}
	resp := &vehicle_pb.GetResultResponse{Result: val}
	return resp, nil
}

func (s *DataService) GetTelemetry(ctx context.Context, req *vehicle_pb.GetTelemetryRequest) (*vehicle_pb.GetTelemetryResponse, error) {
	s.tel_mu.RLock()
	defer s.tel_mu.RUnlock()
	if s.latest_telemetry == nil {
		return nil, fmt.Errorf("telemetry unavailable")
	}
	resp := &vehicle_pb.GetTelemetryResponse{Telemetry: s.latest_telemetry}
	return resp, nil
}

func (s *DataService) GetFrame(ctx context.Context, req *vehicle_pb.GetFrameRequest) (*vehicle_pb.GetFrameResponse, error) {
	s.frame_mu.RLock()
	defer s.frame_mu.RUnlock()
	if s.latest_frame == nil {
		return nil, fmt.Errorf("frame unavilable")
	}
	resp := &vehicle_pb.GetFrameResponse{Frame: s.latest_frame}
	return resp, nil
}

// Encapsulates telemetry stream response along with an error for sending
// in a channel
type TelemetryStreamResponse struct {
	resp *driver_pb.StreamTelemetryResponse
	err  error
}

// Receive telemetry from a telemetry stream, sending any errors to the
// specified error channel.
func (s *DataService) recvTelemetry(
	ctx context.Context,
	stream grpc.ServerStreamingClient[driver_pb.StreamTelemetryResponse],
	errCh chan error) {
	ch := make(chan TelemetryStreamResponse)
	// Invoke blocking call to receive stream data in another goroutine
	go func() {
		resp, err := stream.Recv()
		ch <- TelemetryStreamResponse{resp: resp, err: err}
	}()

	// Wait to receive stream data or context to end
	select {
	case <-ctx.Done():
		s.vehicle.logger.Err(ctx.Err()).Msg("telemetry stream ended")
		errCh <- ctx.Err()
		return
	case res := <-ch:
		if res.err == io.EOF {
			s.vehicle.logger.Err(res.err).Msg("telemetry stream ended")
			errCh <- res.err
			return
		}
		if res.err != nil {
			s.vehicle.logger.Err(res.err).Msg("telemetry stream error")
			errCh <- res.err
			return
		}
		s.updateLatestTelemetry(res.resp.Telemetry)
	}
}

func (s *DataService) updateLatestTelemetry(tel *stream_msg_pb.Telemetry) {
	s.tel_mu.Lock()
	defer s.tel_mu.Unlock()

	s.latest_telemetry = tel
}

func (s *DataService) updateLatestFrame() {
	s.frame_mu.Lock()
	defer s.frame_mu.Unlock()
}

func (s *DataService) updateLatestResults() {
	s.result_mu.Lock()
	defer s.result_mu.Unlock()

}
