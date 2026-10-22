package vehicle

import (
	"context"
	"io"
	"net"
	"os"
	"path/filepath"
	"testing"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// testMissionEnv makes the test binary run as a mission plugin, so that it can
// be loaded as a mission.
const testMissionEnv = "STEELEAGLE_TEST_MISSION"

func TestMain(m *testing.M) {
	if os.Getenv(testMissionEnv) != "" {
		runTestMission()
		return
	}
	os.Exit(m.Run())
}

// testMission is a mission service that starts, and fails to stop with an
// Aborted error naming its file, so a test can tell which mission it called.
type testMission struct {
	missionpb.UnimplementedMissionServiceServer
}

func (testMission) StartMission(
	ctx context.Context,
	req *missionpb.StartMissionRequest,
) (*missionpb.StartMissionResponse, error) {
	return &missionpb.StartMissionResponse{}, nil
}

func (testMission) StopMission(
	ctx context.Context,
	req *missionpb.StopMissionRequest,
) (*missionpb.StopMissionResponse, error) {
	return nil, status.Error(codes.Aborted, filepath.Base(os.Args[0]))
}

// startTestVehicle creates and starts a vehicle with a fake driver, which is
// stopped when the test ends.
func startTestVehicle(t *testing.T) *Vehicle {
	t.Helper()
	v, _ := newTestVehicle(t)
	ctx, cancel := context.WithCancel(context.Background())
	if err := v.Start(ctx, nil); err != nil {
		cancel()
		t.Fatal(err)
	}
	t.Cleanup(func() {
		cancel()
		waitTimeout(t, v)
	})
	return v
}

// loadTestMission saves the test binary as the mission name, and loads it.
func loadTestMission(t *testing.T, v *Vehicle, name string) {
	t.Helper()
	t.Setenv(testMissionEnv, "1")
	copyTestMission(t, v, name)
	req := vehiclepb.LoadMissionRequest_builder{Name: name}.Build()
	if _, err := v.LoadMission(context.Background(), req); err != nil {
		t.Fatalf("load %s: %v", name, err)
	}
}

// runTestMission serves the mission service on the socket the vehicle dials.
func runTestMission() {
	ln, err := net.Listen("unix", os.Getenv(plugin.ListenSockEnv))
	if err != nil {
		os.Exit(1)
	}
	server := grpc.NewServer()
	missionpb.RegisterMissionServiceServer(server, testMission{})
	server.Serve(ln)
}

// copyTestMission saves the test binary in the mission directory as name,
// without execute permission, as an upload is saved.
func copyTestMission(t *testing.T, v *Vehicle, name string) {
	t.Helper()
	self, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(self)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(v.MissionDir, name), data, 0600); err != nil {
		t.Fatal(err)
	}
}

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

// TestLoadMission ensures that a loaded mission runs, that loading another
// mission replaces it, and that the active mission is listed.
func TestLoadMission(t *testing.T) {
	v := startTestVehicle(t)
	loadTestMission(t, v, "first")
	first := v.mission.obj
	if !first.Running() {
		t.Fatal("first mission not running after it was loaded")
	}
	loadTestMission(t, v, "second")
	if first.Running() {
		t.Error("first mission still running after it was replaced")
	}
	if !v.mission.obj.Running() {
		t.Error("second mission not running after it was loaded")
	}

	resp, err := v.GetMissions(context.Background(), &vehiclepb.GetMissionsRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if got := resp.GetActiveMission().GetName(); got != "second" {
		t.Errorf("active mission is %q, want second", got)
	}
	if got := resp.GetMissions(); len(got) != 2 || got[0].GetHash() != got[1].GetHash() {
		t.Errorf("got missions %v, want first and second with the same hash", got)
	}
}

// TestLoadMissionInvalid ensures that only missions in the mission directory
// can be loaded.
func TestLoadMissionInvalid(t *testing.T) {
	v := startTestVehicle(t)
	for name, code := range map[string]codes.Code{
		"":           codes.InvalidArgument,
		"../mission": codes.InvalidArgument,
		".hidden":    codes.InvalidArgument,
		"missing":    codes.NotFound,
	} {
		req := vehiclepb.LoadMissionRequest_builder{Name: name}.Build()
		if _, err := v.LoadMission(context.Background(), req); status.Code(err) != code {
			t.Errorf("mission %q: got %v, want %v", name, err, code)
		}
	}
}
