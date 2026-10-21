package vehicle

import (
	"context"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// UploadMission uploads a mission over the network and saves it to MissionDir.
func (v *Vehicle) UploadMission(
	stream grpc.BidiStreamingServer[vehiclepb.UploadMissionRequest, vehiclepb.UploadMissionResponse],
) error {
	// TODO: implement
	return status.Error(codes.Unimplemented, "UploadMission not implemented")
}

// LoadMission loads a mission from MissionDir by exact name.
func (v *Vehicle) LoadMission(
	ctx context.Context,
	req *vehiclepb.LoadMissionRequest,
) (*vehiclepb.LoadMissionResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "LoadMission not implemented")
}

// GetMissions lists the missions in MissionDir and the active mission.
func (v *Vehicle) GetMissions(
	ctx context.Context,
	req *vehiclepb.GetMissionsRequest,
) (*vehiclepb.GetMissionsResponse, error) {
	// TODO: implement
	return nil, status.Error(codes.Unimplemented, "GetMissions not implemented")
}
