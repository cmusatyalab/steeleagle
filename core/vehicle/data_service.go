package vehicle

import (
	"context"
	"fmt"
	"io"
	"sync"

	result_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/result"
	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
	data_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/data"
	stream_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/stream"
	"github.com/rs/zerolog/log"
)

type DataService struct {
	data_pb.UnimplementedDataServiceServer
	vehicle          *Vehicle
	latest_telemetry *stream_msg_pb.Telemetry
	latest_frame     *stream_msg_pb.EncodedFrame
	latest_results   map[string]*result_pb.ComputeResult
	tel_mu           *sync.RWMutex
	frame_mu         *sync.RWMutex
	result_mu        *sync.RWMutex
}

func (s *DataService) GetResult(ctx context.Context, req *data_pb.GetResultRequest) (*data_pb.GetResultResponse, error) {
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
	resp := &data_pb.GetResultResponse{Result: val}
	return resp, nil
}

func (s *DataService) GetTelemetry(ctx context.Context, req *data_pb.GetTelemetryRequest) (*data_pb.GetTelemetryResponse, error) {
	s.tel_mu.RLock()
	defer s.tel_mu.RUnlock()
	if s.latest_telemetry == nil {
		return nil, fmt.Errorf("telemetry unavailable")
	}
	resp := &data_pb.GetTelemetryResponse{Telemetry: s.latest_telemetry}
	return resp, nil
}

func (s *DataService) GetFrame(ctx context.Context, req *data_pb.GetFrameRequest) (*data_pb.GetFrameResponse, error) {
	s.frame_mu.RLock()
	defer s.frame_mu.RUnlock()
	if s.latest_frame == nil {
		return nil, fmt.Errorf("frame unavilable")
	}
	resp := &data_pb.GetFrameResponse{Frame: s.latest_frame}
	return resp, nil
}

func (s *DataService) StartStreaming(ctx context.Context) error {
	client := stream_pb.NewStreamServiceClient(s.vehicle.conns.driver)
	req := &stream_pb.GetTelemetryStreamRequest{}
	stream, err := client.GetTelemetryStream(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to start stream: %w", err)
	}

	go func() {
		for {
			if err := ctx.Err(); err != nil {
				log.Err(err).Msg("telemetry stream ended")
				return
			}
			res, err := stream.Recv()
			if err == io.EOF {
				log.Err(err).Str("vehicle", s.vehicle.Name()).Msg("telemetry stream ended")
				return
			}
			if err != nil {
				log.Err(err).Msg("telemetry streaming error")
			}
			s.updateLatestTelemetry(res.Telemetry)
		}
	}()
	return nil
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
