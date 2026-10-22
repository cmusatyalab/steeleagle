package vehicle

import (
	"context"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// StartMission starts the loaded mission, relaying the call to its plugin.
func (v *Vehicle) StartMission(
	ctx context.Context,
	req *missionpb.StartMissionRequest,
) (*missionpb.StartMissionResponse, error) {
	client, err := v.missionClient()
	if err != nil {
		return nil, err
	}
	return client.StartMission(ctx, req)
}

// StopMission stops the loaded mission, relaying the call to its plugin.
func (v *Vehicle) StopMission(
	ctx context.Context,
	req *missionpb.StopMissionRequest,
) (*missionpb.StopMissionResponse, error) {
	client, err := v.missionClient()
	if err != nil {
		return nil, err
	}
	return client.StopMission(ctx, req)
}

// missionClient returns a client of the loaded mission's plugin, if it is
// running. The lock is not held during the call, so a slow mission doesn't
// hold up loading another; a mission replaced meanwhile fails the call.
func (v *Vehicle) missionClient() (missionpb.MissionServiceClient, error) {
	v.missionMu.Lock()
	defer v.missionMu.Unlock()
	if v.mission == nil || !v.mission.obj.Running() {
		return nil, status.Error(codes.FailedPrecondition, "No mission loaded")
	}
	return missionpb.NewMissionServiceClient(v.mission.conn), nil
}
