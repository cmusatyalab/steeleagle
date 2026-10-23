package fsm

import (
	"context"
	"fmt"
	"net"
	"sync"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// server serves a mission's MissionService to the vehicle. StartMission sets
// the mission's dataflow, if it has one, and starts a new run of the
// mission; StopMission stops the current run, after which the mission can be
// started again.
type server struct {
	missionpb.UnimplementedMissionServiceServer
	newMission func() *DslFsm              // creates a run of the mission
	flowToml   []byte                      // dataflow set on each start, if any
	data       vehiclepb.DataServiceClient // vehicle data service to set the dataflow with
	log        zerolog.Logger
	ctx        context.Context // context of Serve, which scopes every run
	exit       chan error      // receives why Serve should return, nil once the mission completes
	mu         sync.Mutex      // protects closed, cancel and done
	closed     bool            // whether Serve is returning, so no run may start
	cancel     context.CancelFunc
	done       chan struct{} // closed once the current run ends, nil if none is running
}

// Serve serves the mission's MissionService on ln until the mission
// completes, fails, or ctx is canceled. Each StartMission sets the dataflow
// flowToml over conn, if it isn't empty, then runs a new mission from
// newMission. Serve returns nil once a run completes or ctx is canceled, and
// an error once a run fails or the dataflow can't be set, so the mission
// process can exit.
func Serve(
	ctx context.Context,
	ln net.Listener,
	conn *grpc.ClientConn,
	flowToml []byte,
	log zerolog.Logger,
	newMission func() *DslFsm,
) error {
	s := &server{
		newMission: newMission,
		flowToml:   flowToml,
		data:       vehiclepb.NewDataServiceClient(conn),
		log:        log,
		ctx:        ctx,
		exit:       make(chan error, 1),
	}
	grpcServer := grpc.NewServer()
	missionpb.RegisterMissionServiceServer(grpcServer, s)
	served := make(chan error, 1)
	go func() { served <- grpcServer.Serve(ln) }()
	log.Info().Str("socket", ln.Addr().String()).Msg("waiting for mission start")

	var err error
	select {
	case <-ctx.Done():
		log.Info().Msg("mission process stopping")
	case err = <-s.exit:
	case err = <-served:
		err = fmt.Errorf("serving mission service: %w", err)
	}
	// The run is stopped first, which ends any StopMission call waiting on
	// it, so the graceful stop still sends the calls in flight their
	// responses, such as the error of the StartMission that ended Serve
	s.mu.Lock()
	s.closed = true
	s.mu.Unlock()
	s.stopRun()
	grpcServer.GracefulStop()
	return err
}

// StartMission sets the mission's dataflow, if it has one, and starts a new
// run of the mission. A dataflow that can't be set makes Serve return.
func (s *server) StartMission(
	ctx context.Context,
	req *missionpb.StartMissionRequest,
) (*missionpb.StartMissionResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return nil, status.Error(codes.Unavailable, "mission is exiting")
	}
	if s.done != nil {
		return nil, status.Error(codes.FailedPrecondition, "mission already running")
	}
	if len(s.flowToml) > 0 {
		req := vehiclepb.SetDataflowRequest_builder{Toml: s.flowToml}.Build()
		if _, err := s.data.SetDataflow(ctx, req); err != nil {
			s.log.Error().Err(err).Msg("could not set mission dataflow, exiting")
			s.exitWith(fmt.Errorf("setting mission dataflow: %w", err))
			return nil, err
		}
		s.log.Info().Msg("mission dataflow set")
	}

	runCtx, cancel := context.WithCancel(s.ctx)
	done := make(chan struct{})
	s.cancel, s.done = cancel, done
	mission := s.newMission()
	go func() {
		err := mission.Start(runCtx)
		stopped := runCtx.Err() != nil
		cancel()
		s.mu.Lock()
		s.cancel, s.done = nil, nil
		s.mu.Unlock()
		close(done)
		switch {
		case stopped:
			// Tasks fail with the canceled context when a run is stopped, so
			// that error is expected
			s.log.Info().AnErr("result", err).Msg("mission stopped")
		case err != nil:
			s.exitWith(err)
		default:
			s.log.Info().Msg("mission complete")
			s.exitWith(nil)
		}
	}()
	s.log.Info().Msg("mission started")
	return &missionpb.StartMissionResponse{}, nil
}

// StopMission stops the current run of the mission, if any, and waits for
// it to end.
func (s *server) StopMission(
	ctx context.Context,
	req *missionpb.StopMissionRequest,
) (*missionpb.StopMissionResponse, error) {
	s.mu.Lock()
	cancel, done := s.cancel, s.done
	s.mu.Unlock()
	if done == nil {
		s.log.Debug().Msg("stop with no mission running")
		return &missionpb.StopMissionResponse{}, nil
	}
	s.log.Info().Msg("stopping mission")
	cancel()
	select {
	case <-done:
		return &missionpb.StopMissionResponse{}, nil
	case <-ctx.Done():
		return nil, status.FromContextError(ctx.Err()).Err()
	}
}

// stopRun stops the current run, if any, and waits for it to end.
func (s *server) stopRun() {
	s.mu.Lock()
	cancel, done := s.cancel, s.done
	s.mu.Unlock()
	if done != nil {
		cancel()
		<-done
	}
}

// exitWith makes Serve return err, unless it has already been given a
// reason to return.
func (s *server) exitWith(err error) {
	select {
	case s.exit <- err:
	default:
	}
}
