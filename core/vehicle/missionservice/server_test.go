package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
)

// wantCode fails the test unless err is a gRPC status error with the given
// code.
func wantCode(t *testing.T, err error, code codes.Code) {
	t.Helper()
	if status.Code(err) != code {
		t.Fatalf("got error %v, want code %s", err, code)
	}
}

// upload reads the built mock mission binary and uploads it to s.
func upload(t *testing.T, s *server) {
	t.Helper()
	data, err := os.ReadFile(mockMissionBinary)
	if err != nil {
		t.Fatalf("reading mock mission binary: %v", err)
	}
	if _, err := s.UploadMission(t.Context(), missionpb.UploadMissionRequest_builder{
		Mission: missionpb.MissionData_builder{Binary: data}.Build(),
	}.Build()); err != nil {
		t.Fatalf("UploadMission: %v", err)
	}
}

func TestUploadMissionRejectsEmptyPayload(t *testing.T) {
	s := newServer("", t.TempDir())
	_, err := s.UploadMission(t.Context(), missionpb.UploadMissionRequest_builder{
		Mission: missionpb.MissionData_builder{}.Build(),
	}.Build())
	wantCode(t, err, codes.InvalidArgument)
}

func TestStartMissionWithoutUpload(t *testing.T) {
	s := newServer("", t.TempDir())
	_, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{})
	wantCode(t, err, codes.FailedPrecondition)
}

func TestStopMissionWithoutRunningIsNoop(t *testing.T) {
	s := newServer("", t.TempDir())
	if _, err := s.StopMission(t.Context(), &missionpb.StopMissionRequest{}); err != nil {
		t.Fatalf("StopMission with nothing running: %v", err)
	}
}

// TestStartMissionRunsBinaryWithClientSocket uploads the mock mission binary,
// starts it, and confirms it actually ran and received the client socket
// missionservice was configured with.
func TestStartMissionRunsBinaryWithClientSocket(t *testing.T) {
	runDir := t.TempDir()
	marker := filepath.Join(runDir, "marker")
	t.Setenv("MOCK_MISSION_MARKER", marker)
	t.Setenv("MOCK_MISSION_BLOCK", "1")

	s := newServer("/tmp/fake-client.sock", runDir)
	upload(t, s)

	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission: %v", err)
	}
	t.Cleanup(func() { s.stop(context.Background()) })

	deadline := time.After(5 * time.Second)
	for {
		data, err := os.ReadFile(marker)
		if err == nil {
			if got := string(data); got != s.clientSocket {
				t.Fatalf("mission subprocess saw client socket %q, want %q", got, s.clientSocket)
			}
			break
		}
		select {
		case <-deadline:
			t.Fatalf("mock mission binary never wrote its marker: %v", err)
		case <-time.After(20 * time.Millisecond):
		}
	}
}

// TestStartMissionAlreadyRunning confirms a second StartMission is rejected
// while the first mission is still running.
func TestStartMissionAlreadyRunning(t *testing.T) {
	runDir := t.TempDir()
	t.Setenv("MOCK_MISSION_MARKER", filepath.Join(runDir, "marker"))
	t.Setenv("MOCK_MISSION_BLOCK", "1")

	s := newServer("", runDir)
	upload(t, s)
	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission: %v", err)
	}
	t.Cleanup(func() { s.stop(context.Background()) })

	_, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{})
	wantCode(t, err, codes.FailedPrecondition)
}

// TestUploadMissionWhileRunning confirms UploadMission is rejected while a
// mission is running, so it can't be swapped out from under a live run.
func TestUploadMissionWhileRunning(t *testing.T) {
	runDir := t.TempDir()
	t.Setenv("MOCK_MISSION_MARKER", filepath.Join(runDir, "marker"))
	t.Setenv("MOCK_MISSION_BLOCK", "1")

	s := newServer("", runDir)
	upload(t, s)
	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission: %v", err)
	}
	t.Cleanup(func() { s.stop(context.Background()) })

	data, err := os.ReadFile(mockMissionBinary)
	if err != nil {
		t.Fatalf("reading mock mission binary: %v", err)
	}
	_, err = s.UploadMission(t.Context(), missionpb.UploadMissionRequest_builder{
		Mission: missionpb.MissionData_builder{Binary: data}.Build(),
	}.Build())
	wantCode(t, err, codes.FailedPrecondition)
}

// TestStopMissionKillsSubprocessAndAllowsRestart confirms StopMission
// terminates a still-running mission and that the server accepts a fresh
// StartMission afterward.
func TestStopMissionKillsSubprocessAndAllowsRestart(t *testing.T) {
	runDir := t.TempDir()
	t.Setenv("MOCK_MISSION_MARKER", filepath.Join(runDir, "marker"))
	t.Setenv("MOCK_MISSION_BLOCK", "1")

	s := newServer("", runDir)
	upload(t, s)
	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission: %v", err)
	}

	if _, err := s.StopMission(t.Context(), &missionpb.StopMissionRequest{}); err != nil {
		t.Fatalf("StopMission: %v", err)
	}

	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission after stop: %v", err)
	}
	t.Cleanup(func() { s.stop(context.Background()) })
}

// TestMissionExitOnItsOwnClearsState confirms a mission that exits by itself
// (rather than being stopped) still clears run state so a new one can start.
func TestMissionExitOnItsOwnClearsState(t *testing.T) {
	runDir := t.TempDir()
	t.Setenv("MOCK_MISSION_MARKER", filepath.Join(runDir, "marker"))
	t.Setenv("MOCK_MISSION_BLOCK", "0")

	s := newServer("", runDir)
	upload(t, s)
	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission: %v", err)
	}

	deadline := time.After(5 * time.Second)
	for {
		s.mu.Lock()
		running := s.cancel != nil
		s.mu.Unlock()
		if !running {
			break
		}
		select {
		case <-deadline:
			t.Fatal("mission never cleared run state after exiting on its own")
		case <-time.After(20 * time.Millisecond):
		}
	}

	if _, err := s.StartMission(t.Context(), &missionpb.StartMissionRequest{}); err != nil {
		t.Fatalf("StartMission after previous mission exited: %v", err)
	}
	t.Cleanup(func() { s.stop(context.Background()) })
}
