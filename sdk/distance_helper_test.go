package sdk

import (
	"math"
	"testing"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
)

// telemetryGlobal injects a GlobalPosition into a Telemetry object.
func telemetryGlobal(gp *commonpb.GlobalPosition) *telemetrypb.Telemetry {
	return telemetrypb.Telemetry_builder{
		PositionInfo: telemetrypb.PositionInfo_builder{GlobalPosition: gp}.Build(),
	}.Build()
}

// telemetryRelative injects a RelativePosition into a Telemetry object.
func telemetryRelative(rp *commonpb.RelativePosition) *telemetrypb.Telemetry {
	return telemetrypb.Telemetry_builder{
		PositionInfo: telemetrypb.PositionInfo_builder{RelativePosition: rp}.Build(),
	}.Build()
}

// telemetryVelocity injects a Velocity into a Telemetry object.
func telemetryVelocity(v *commonpb.Velocity) *telemetrypb.Telemetry {
	return telemetrypb.Telemetry_builder{
		PositionInfo: telemetrypb.PositionInfo_builder{VelocityNeu: v}.Build(),
	}.Build()
}

// telemetryPose injects a Pose into a Telemetry object.
func telemetryPose(p *commonpb.Pose) *telemetrypb.Telemetry {
	return telemetrypb.Telemetry_builder{
		GimbalInfo: telemetrypb.GimbalInfo_builder{PoseNeu: p}.Build(),
	}.Build()
}

// telemetryPoseVelocity injects a PoseVelocity into a Telemetry object.
func telemetryPoseVelocity(pv *commonpb.PoseVelocity) *telemetrypb.Telemetry {
	return telemetrypb.Telemetry_builder{
		GimbalInfo: telemetrypb.GimbalInfo_builder{AngularVelocityNeu: pv}.Build(),
	}.Build()
}

// assertApproaching walks a sequence of getDistance calls that simulate a
// drone moving steadily toward a setpoint, and checks that the returned
// normalized distance strictly decreases at every step, that the vehicle
// starts out of tolerance, and that it ends within tolerance.
func assertApproaching(t *testing.T, name string, calls []func() (float32, bool, error)) {
	t.Helper()
	var prev float32 = math.MaxFloat32
	for i, call := range calls {
		dist, ok, err := call()
		if err != nil {
			t.Fatalf("%s: step %d: unexpected error: %v", name, i, err)
		}
		if dist >= prev {
			t.Errorf("%s: step %d: distance did not decrease: got %v, previous %v", name, i, dist, prev)
		}
		prev = dist
		if i == 0 && ok {
			t.Errorf("%s: step %d: expected out-of-tolerance start, got ok=true (dist=%v)", name, i, dist)
		}
		if i == len(calls)-1 && !ok {
			t.Errorf("%s: final step: expected within-tolerance finish, got ok=false (dist=%v)", name, dist)
		}
	}
}
