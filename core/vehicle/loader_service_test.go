package vehicle

import (
	"io"
	"os"
	"path/filepath"
	"testing"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// fakeUploadStream is an upload stream that receives reqs and records the
// chunk numbers acknowledged.
type fakeUploadStream struct {
	grpc.ServerStream
	reqs     []*vehiclepb.UploadMissionRequest
	received []int32
}

func (s *fakeUploadStream) Recv() (*vehiclepb.UploadMissionRequest, error) {
	if len(s.reqs) == 0 {
		return nil, io.EOF
	}
	req := s.reqs[0]
	s.reqs = s.reqs[1:]
	return req, nil
}

func (s *fakeUploadStream) Send(resp *vehiclepb.UploadMissionResponse) error {
	s.received = append(s.received, resp.GetReceived())
	return nil
}

// missionChunks splits data into numbered chunks of an upload named name.
func missionChunks(name string, data ...string) []*vehiclepb.UploadMissionRequest {
	var reqs []*vehiclepb.UploadMissionRequest
	for i, d := range data {
		reqs = append(reqs, vehiclepb.UploadMissionRequest_builder{
			Filename: name, Chunk: []byte(d), Number: int32(i + 1), Total: int32(len(data)),
		}.Build())
	}
	return reqs
}

// TestUploadMission ensures that an uploaded mission is saved in full to the
// mission directory under its name, with each chunk acknowledged, and that an
// upload named outside the mission directory is rejected.
func TestUploadMission(t *testing.T) {
	v, _ := newTestVehicle(t)

	stream := &fakeUploadStream{reqs: missionChunks("patrol.ms", "a", "b", "c")}
	if err := v.UploadMission(stream); err != nil {
		t.Fatalf("upload failed: %v", err)
	}
	if len(stream.received) != 3 || stream.received[0] != 1 || stream.received[2] != 3 {
		t.Errorf("expected all 3 chunks acknowledged, got %v", stream.received)
	}
	path := filepath.Join(v.MissionDir, "patrol.ms")
	if got, err := os.ReadFile(path); err != nil || string(got) != "abc" {
		t.Errorf("expected %s to hold %q, got %q, %v", path, "abc", got, err)
	}

	stream = &fakeUploadStream{reqs: missionChunks("../patrol.ms", "a")}
	if err := v.UploadMission(stream); status.Code(err) != codes.InvalidArgument {
		t.Errorf("expected InvalidArgument, got %v", err)
	}
}
