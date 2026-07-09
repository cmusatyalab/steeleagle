package vehicle

import (
	"sync"

	resultpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/result"
	stream_msg_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/messages/stream"
)

// dataStore stores data associated with a vehicle, such as sensor data and
// computed results.
type dataStore struct {
	latest_telemetry *stream_msg_pb.Telemetry
	latest_frame     *stream_msg_pb.EncodedFrame
	latest_results   map[string]*resultpb.ComputeResult
	tel_mu           *sync.RWMutex
	frame_mu         *sync.RWMutex
	result_mu        *sync.RWMutex
}

// Get the latest telemetry available for the vehicle.
func (s *dataStore) getTelemetry() *stream_msg_pb.Telemetry {
	s.tel_mu.RLock()
	defer s.tel_mu.RUnlock()
	return s.latest_telemetry
}

// Get the latest frame available for the vehicle.
func (s *dataStore) getFrame() *stream_msg_pb.EncodedFrame {
	s.frame_mu.RLock()
	defer s.frame_mu.RUnlock()
	return s.latest_frame
}

// Get the latest compute result available for the given producer.
func (s *dataStore) getResult(producerName string) *resultpb.ComputeResult {
	s.result_mu.RLock()
	defer s.result_mu.RUnlock()
	return s.latest_results[producerName]
}

// Update the latest telemetry stored for the vehicle.
func (s *dataStore) updateLatestTelemetry(tel *stream_msg_pb.Telemetry) {
	s.tel_mu.Lock()
	defer s.tel_mu.Unlock()

	s.latest_telemetry = tel
}

// Update the latest frame stored for the vehicle.
func (s *dataStore) updateLatestFrame(frame *stream_msg_pb.EncodedFrame) {
	s.frame_mu.Lock()
	defer s.frame_mu.Unlock()

	s.latest_frame = frame
}

// Update the latest compute result stored for the vehicle.
func (s *dataStore) updateLatestResult(producerName string, res *resultpb.ComputeResult) {
	s.result_mu.Lock()
	defer s.result_mu.Unlock()

	s.latest_results[producerName] = res
}
