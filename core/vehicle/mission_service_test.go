package vehicle

import (
	"context"
	"testing"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TestMissionServiceRelays ensures that the vehicle's mission service relays
// calls, and their results, to the loaded mission, and to a mission that
// replaced it.
func TestMissionServiceRelays(t *testing.T) {
	v := startTestVehicle(t)
	client := missionpb.NewMissionServiceClient(v.adminConn)
	for _, name := range []string{"first", "second"} {
		loadTestMission(t, v, name)
		if _, err := client.StartMission(context.Background(), &missionpb.StartMissionRequest{}); err != nil {
			t.Fatalf("start %s: %v", name, err)
		}
		// The test mission fails to stop with an error naming it
		_, err := client.StopMission(context.Background(), &missionpb.StopMissionRequest{})
		if s := status.Convert(err); s.Code() != codes.Aborted || s.Message() != name {
			t.Errorf("stop %s: got %v, want Aborted from %s", name, err, name)
		}
	}
}

// TestMissionServiceNoMission ensures that the mission service fails without
// a running mission.
func TestMissionServiceNoMission(t *testing.T) {
	v := startTestVehicle(t)
	client := missionpb.NewMissionServiceClient(v.adminConn)
	check := func(when string) {
		t.Helper()
		_, err := client.StartMission(context.Background(), &missionpb.StartMissionRequest{})
		if s := status.Convert(err); s.Code() != codes.FailedPrecondition || s.Message() != "No mission loaded" {
			t.Errorf("start %s: got %v, want No mission loaded", when, err)
		}
		_, err = client.StopMission(context.Background(), &missionpb.StopMissionRequest{})
		if s := status.Convert(err); s.Code() != codes.FailedPrecondition || s.Message() != "No mission loaded" {
			t.Errorf("stop %s: got %v, want No mission loaded", when, err)
		}
	}
	check("before a mission is loaded")

	loadTestMission(t, v, "mission")
	v.mission.cancel()
	v.mission.obj.Wait()
	check("after the mission exited")
}
