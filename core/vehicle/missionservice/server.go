package main

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
)

// stopTimeout bounds how long StopMission and shutdown wait for the mission
// subprocess to exit after it's been signaled.
const stopTimeout = 10 * time.Second

// binaryName is the filename the uploaded mission binary is stored under in
// runDir.
const binaryName = "mission"

// server implements MissionServiceServer, launching an uploaded mission binary
// as a subprocess and tracking its lifecycle.
type server struct {
	missionpb.UnimplementedMissionServiceServer

	clientSocket string // socket the mission subprocess dials to reach control/data services
	runDir       string // directory the uploaded mission binary is stored in

	mu         sync.Mutex
	binaryPath string             // set once UploadMission has stored a binary
	cancel     context.CancelFunc // cancels the running mission's context; nil if nothing is running
	done       chan struct{}      // closed once the running mission's subprocess exits; nil if nothing is running
}

func newServer(clientSocket, runDir string) *server {
	return &server{clientSocket: clientSocket, runDir: runDir}
}

// UploadMission stores req's mission binary, replacing any previously
// uploaded one. Fails if a mission is currently running.
func (s *server) UploadMission(ctx context.Context, req *missionpb.UploadMissionRequest) (*missionpb.UploadMissionResponse, error) {
	data := req.GetMission().GetBinary()
	if len(data) == 0 {
		return nil, status.Error(codes.InvalidArgument, "mission must be a binary payload")
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cancel != nil {
		return nil, status.Error(codes.FailedPrecondition, "cannot upload a new mission while one is running")
	}

	path := filepath.Join(s.runDir, binaryName)
	if err := os.WriteFile(path, data, 0o755); err != nil {
		return nil, status.Errorf(codes.Internal, "writing mission binary: %v", err)
	}
	s.binaryPath = path
	log.Info().Str("path", path).Int("bytes", len(data)).Msg("mission uploaded")
	return &missionpb.UploadMissionResponse{}, nil
}

// StartMission execs the uploaded mission binary as a subprocess, passing it
// this plugin's client socket so it can reach the vehicle's control/data
// services directly. Fails if no mission has been uploaded or one is already
// running.
func (s *server) StartMission(ctx context.Context, req *missionpb.StartMissionRequest) (*missionpb.StartMissionResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cancel != nil {
		return nil, status.Error(codes.FailedPrecondition, "mission already running")
	}
	if s.binaryPath == "" {
		return nil, status.Error(codes.FailedPrecondition, "no mission uploaded")
	}

	runCtx, cancel := context.WithCancel(context.Background())
	cmd := exec.CommandContext(runCtx, s.binaryPath)
	cmd.Env = append(os.Environ(),
		util.ClientSockEnv+"="+s.clientSocket,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	// Run in its own process group and kill the whole group on stop/cancel,
	// not just the immediate child, in case the mission binary spawns its own
	// children.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Cancel = func() error {
		return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}

	if err := cmd.Start(); err != nil {
		cancel()
		return nil, status.Errorf(codes.Internal, "starting mission binary: %v", err)
	}

	done := make(chan struct{})
	s.cancel = cancel
	s.done = done
	go s.watch(cmd, done)

	log.Info().Str("path", s.binaryPath).Int("pid", cmd.Process.Pid).Msg("mission started")
	return &missionpb.StartMissionResponse{}, nil
}

// watch waits for cmd to exit, logs the result, and clears the running-mission
// state so a subsequent StartMission is allowed.
func (s *server) watch(cmd *exec.Cmd, done chan struct{}) {
	err := cmd.Wait()
	if err != nil {
		log.Warn().Err(err).Msg("mission exited")
	} else {
		log.Info().Msg("mission exited")
	}
	close(done)

	s.mu.Lock()
	defer s.mu.Unlock()
	// Only clear state if this run is still the current one. A concurrent
	// StopMission/StartMission may have already replaced it.
	if s.done == done {
		s.cancel = nil
		s.done = nil
	}
}

// StopMission stops the running mission, if any, and waits for its subprocess
// to exit. A no-op if no mission is running.
func (s *server) StopMission(ctx context.Context, req *missionpb.StopMissionRequest) (*missionpb.StopMissionResponse, error) {
	if err := s.stop(ctx); err != nil {
		return nil, err
	}
	return &missionpb.StopMissionResponse{}, nil
}

// stop is StopMission's implementation, also used for shutdown.
func (s *server) stop(ctx context.Context) error {
	s.mu.Lock()
	cancel, done := s.cancel, s.done
	s.mu.Unlock()
	if cancel == nil {
		return nil
	}

	cancel()
	select {
	case <-done:
		return nil
	case <-time.After(stopTimeout):
		return status.Errorf(codes.DeadlineExceeded, "mission did not stop within %s", stopTimeout)
	}
}
