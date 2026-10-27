package vehicle

import (
	"context"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// StartMission starts the loaded mission, putting the vehicle in autonomous
// control mode until the mission is stopped.
func (v *Vehicle) StartMission(
	ctx context.Context,
	req *missionpb.StartMissionRequest,
) (*missionpb.StartMissionResponse, error) {
	v.missionMu.Lock()
	defer v.missionMu.Unlock()
	if v.mission == nil {
		return nil, status.Error(codes.FailedPrecondition, "no mission loaded")
	}
	if v.mission.Running() {
		return nil, status.Error(codes.FailedPrecondition, "mission already running")
	}
	// A stopping vehicle stops its mission once it holds missionMu, so none is
	// started after that
	if v.ctx.Err() != nil {
		return nil, status.Error(codes.Unavailable, "vehicle is stopping")
	}
	v.stopMission() // clean up after a mission that exited on its own

	// The mission lives until it is stopped or the run stops, not as long as
	// this call
	missionCtx, cancel := context.WithCancel(v.ctx)
	ln, conn, err := v.mission.Start(missionCtx)
	if err != nil {
		cancel()
		v.log.Error().Err(err).Str("mission", v.missionName).Msg("could not start mission plugin")
		return nil, status.Error(codes.Internal, err.Error())
	}
	v.missionInfo = &pluginInfo{ln: ln, conn: conn, cancel: cancel}

	// The mission calls the vehicle's services through its listener
	go func() {
		if err := v.server.Serve(ln); err != nil {
			v.log.Debug().Err(err).Str("listener", "mission").Msg("listener closed")
		}
	}()
	v.log.Info().Str("mission", v.missionName).Msg("mission started")
	return &missionpb.StartMissionResponse{}, nil
}

// StopMission stops the running mission, putting the vehicle back in manual
// control mode.
func (v *Vehicle) StopMission(
	ctx context.Context,
	req *missionpb.StopMissionRequest,
) (*missionpb.StopMissionResponse, error) {
	v.missionMu.Lock()
	defer v.missionMu.Unlock()
	if v.mission == nil {
		return nil, status.Error(codes.FailedPrecondition, "no mission loaded")
	}
	v.stopMission()
	return &missionpb.StopMissionResponse{}, nil
}

// stopMission stops the mission plugin and closes its connections, if it was
// started. The caller must hold missionMu.
func (v *Vehicle) stopMission() {
	if v.missionInfo == nil {
		return
	}
	v.missionInfo.cancel()
	v.mission.Wait()
	v.missionInfo.conn.Close()
	v.missionInfo = nil
	v.log.Info().Str("mission", v.missionName).Msg("mission stopped")
}
