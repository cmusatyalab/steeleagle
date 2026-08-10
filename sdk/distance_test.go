package sdk

import (
	"errors"
	"math"
	"testing"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// TestDistanceGlobalPositionApproaching tests a getDistance call for
// a sequence of GlobalPositions.
func TestDistanceGlobalPositionApproaching(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{
		Latitude: f64(37.0000), Longitude: f64(-122.0000), Altitude: f32(100), Heading: f32(90),
	}.Build()
	tol := opt.Tolerances{PosTol: 5, AngleTol: 5}

	steps := []*commonpb.GlobalPosition{
		commonpb.GlobalPosition_builder{Latitude: f64(37.0050), Longitude: f64(-122.0050), Altitude: f32(250), Heading: f32(270)}.Build(),
		commonpb.GlobalPosition_builder{Latitude: f64(37.0010), Longitude: f64(-122.0010), Altitude: f32(150), Heading: f32(180)}.Build(),
		commonpb.GlobalPosition_builder{Latitude: f64(37.0001), Longitude: f64(-122.0001), Altitude: f32(102), Heading: f32(95)}.Build(),
		commonpb.GlobalPosition_builder{Latitude: f64(37.00001), Longitude: f64(-122.00001), Altitude: f32(100.5), Heading: f32(91)}.Build(),
	}

	calls := make([]func() (float32, bool, error), len(steps))
	for i, gp := range steps {
		gp := gp
		calls[i] = func() (float32, bool, error) { return getDistance(setpoint, telemetryGlobal(gp), tol) }
	}
	assertApproaching(t, "GlobalPosition", calls)
}

// TestDistanceRelativePositionApproaching tests a getDistance call for
// a sequence of RelativePositions.
func TestDistanceRelativePositionApproaching(t *testing.T) {
	setpoint := commonpb.RelativePosition_builder{
		X: f32(10), Y: f32(-10), Z: f32(5), Angle: f32(45),
	}.Build()
	tol := opt.Tolerances{PosTol: 2, AngleTol: 5}

	steps := []*commonpb.RelativePosition{
		commonpb.RelativePosition_builder{X: f32(100), Y: f32(-100), Z: f32(50), Angle: f32(225)}.Build(),
		commonpb.RelativePosition_builder{X: f32(30), Y: f32(-30), Z: f32(15), Angle: f32(90)}.Build(),
		commonpb.RelativePosition_builder{X: f32(12), Y: f32(-12), Z: f32(6), Angle: f32(50)}.Build(),
		commonpb.RelativePosition_builder{X: f32(10.5), Y: f32(-10.4), Z: f32(5.2), Angle: f32(46)}.Build(),
	}

	calls := make([]func() (float32, bool, error), len(steps))
	for i, rp := range steps {
		rp := rp
		calls[i] = func() (float32, bool, error) { return getDistance(setpoint, telemetryRelative(rp), tol) }
	}
	assertApproaching(t, "RelativePosition", calls)
}

// TestDistanceVelocityApproaching tests a getDistance call for
// a sequence of Velocities.
func TestDistanceVelocityApproaching(t *testing.T) {
	setpoint := commonpb.Velocity_builder{
		XVel: f32(5), YVel: f32(-3), ZVel: f32(1), AngularVel: f32(20),
	}.Build()
	tol := opt.Tolerances{SpeedTol: 1, AngSpeedTol: 5}

	steps := []*commonpb.Velocity{
		commonpb.Velocity_builder{XVel: f32(50), YVel: f32(-30), ZVel: f32(10), AngularVel: f32(200)}.Build(),
		commonpb.Velocity_builder{XVel: f32(15), YVel: f32(-9), ZVel: f32(3), AngularVel: f32(60)}.Build(),
		commonpb.Velocity_builder{XVel: f32(6), YVel: f32(-3.5), ZVel: f32(1.2), AngularVel: f32(23)}.Build(),
		commonpb.Velocity_builder{XVel: f32(5.1), YVel: f32(-3.05), ZVel: f32(1.02), AngularVel: f32(20.5)}.Build(),
	}

	calls := make([]func() (float32, bool, error), len(steps))
	for i, v := range steps {
		v := v
		calls[i] = func() (float32, bool, error) { return getDistance(setpoint, telemetryVelocity(v), tol) }
	}
	assertApproaching(t, "Velocity", calls)
}

// TestDistancePoseApproaching tests a getDistance call for
// a sequence of Poses.
func TestDistancePoseApproaching(t *testing.T) {
	setpoint := commonpb.Pose_builder{
		Pitch: f32(10), Roll: f32(-5), Yaw: f32(350),
	}.Build()
	tol := opt.Tolerances{AngleTol: 4}

	steps := []*commonpb.Pose{
		commonpb.Pose_builder{Pitch: f32(100), Roll: f32(-95), Yaw: f32(170)}.Build(),
		commonpb.Pose_builder{Pitch: f32(40), Roll: f32(-35), Yaw: f32(260)}.Build(),
		commonpb.Pose_builder{Pitch: f32(14), Roll: f32(-9), Yaw: f32(340)}.Build(),
		commonpb.Pose_builder{Pitch: f32(10.5), Roll: f32(-5.4), Yaw: f32(349)}.Build(),
	}

	calls := make([]func() (float32, bool, error), len(steps))
	for i, p := range steps {
		p := p
		calls[i] = func() (float32, bool, error) { return getDistance(setpoint, telemetryPose(p), tol) }
	}
	assertApproaching(t, "Pose", calls)
}

// TestDistancePoseVelocityApproaching tests a getDistance call for
// a sequence of PoseVelocities.
func TestDistancePoseVelocityApproaching(t *testing.T) {
	setpoint := commonpb.PoseVelocity_builder{
		PitchVel: f32(2), RollVel: f32(-1), YawVel: f32(8),
	}.Build()
	tol := opt.Tolerances{AngSpeedTol: 2}

	steps := []*commonpb.PoseVelocity{
		commonpb.PoseVelocity_builder{PitchVel: f32(20), RollVel: f32(-10), YawVel: f32(80)}.Build(),
		commonpb.PoseVelocity_builder{PitchVel: f32(6), RollVel: f32(-3), YawVel: f32(24)}.Build(),
		commonpb.PoseVelocity_builder{PitchVel: f32(2.5), RollVel: f32(-1.2), YawVel: f32(9)}.Build(),
		commonpb.PoseVelocity_builder{PitchVel: f32(2.05), RollVel: f32(-1.02), YawVel: f32(8.1)}.Build(),
	}

	calls := make([]func() (float32, bool, error), len(steps))
	for i, pv := range steps {
		pv := pv
		calls[i] = func() (float32, bool, error) { return getDistance(setpoint, telemetryPoseVelocity(pv), tol) }
	}
	assertApproaching(t, "PoseVelocity", calls)
}

// TestDistancePoseYawWraparound guards against a regression to naive
// angle subtraction: 1 degree and 359 degrees are only 2 degrees apart going
// through 0/360, not 358 degrees apart.
func TestDistancePoseYawWraparound(t *testing.T) {
	setpoint := commonpb.Pose_builder{Yaw: f32(1)}.Build()
	tol := opt.Tolerances{AngleTol: 5}
	telemetry := telemetryPose(commonpb.Pose_builder{Yaw: f32(359)}.Build())

	dist, ok, err := getDistance(setpoint, telemetry, tol)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Errorf("expected wraparound distance to be within tolerance, got ok=false (dist=%v)", dist)
	}
	if dist < 0.3 || dist > 0.5 {
		t.Errorf("expected normalized distance ~0.4 (2deg/5deg tol), got %v", dist)
	}
}

// TestDistanceGlobalPositionHaversine checks getDistance's horizontal
// distance calculation against an independent reference: for two points on
// the same meridian (equal longitude), the great-circle distance reduces
// exactly to the meridian arc length R*deltaLat, regardless of the
// haversine implementation details.
func TestDistanceGlobalPositionHaversine(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
	telemetry := telemetryGlobal(commonpb.GlobalPosition_builder{Latitude: f64(0.01), Longitude: f64(0)}.Build())
	tol := opt.Tolerances{PosTol: 1} // PosTol=1 means the returned distance equals raw meters.

	const earthRadiusM = 6371000.0
	expectedMeters := earthRadiusM * (0.01 * math.Pi / 180)

	dist, ok, err := getDistance(setpoint, telemetry, tol)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Errorf("expected out-of-tolerance result with PosTol=1, got ok=true (dist=%v)", dist)
	}
	if diff := math.Abs(float64(dist) - expectedMeters); diff > 1 {
		t.Errorf("expected distance ~%.3fm, got %.3fm (diff %.3fm)", expectedMeters, dist, diff)
	}
}

// TestDistanceUnsupportedSetpoint checks to ensure an ErrInternal is returned if an
// unexpected setpoint type is passed in.
func TestDistanceUnsupportedSetpointType(t *testing.T) {
	// A Telemetry message is a valid proto.Message but not one of the
	// setpoint types getDistance switches on.
	unsupported := telemetrypb.Telemetry_builder{}.Build()
	telemetry := telemetryGlobal(commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build())

	dist, ok, err := getDistance(unsupported, telemetry, opt.Tolerances{PosTol: 1})
	if !errors.Is(err, ErrInternal) {
		t.Fatalf("expected ErrInternal, got %v", err)
	}
	if ok {
		t.Errorf("expected ok=false, got true")
	}
	if dist != 0 {
		t.Errorf("expected dist=0, got %v", dist)
	}
}

// TestDistanceMissingPositionInfo checks to ensure an ErrInternal is returned if
// there is no PositionInfo in a Telemetry message for an action/guidance setpoint.
func TestDistanceMissingPositionInfo(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
	emptyTelemetry := telemetrypb.Telemetry_builder{}.Build()

	_, _, err := getDistance(setpoint, emptyTelemetry, opt.Tolerances{PosTol: 1})
	if !errors.Is(err, ErrInternal) {
		t.Fatalf("expected ErrInternal, got %v", err)
	}
}

// TestDistanceMissingGimbalInfo checks to ensure an ErrInternal is returned if
// there is no GimbalInfo in a Telemetry message for a gimbal setpoint.
func TestDistanceMissingGimbalInfo(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(0)}.Build()
	emptyTelemetry := telemetrypb.Telemetry_builder{}.Build()

	_, _, err := getDistance(setpoint, emptyTelemetry, opt.Tolerances{AngleTol: 1})
	if !errors.Is(err, ErrInternal) {
		t.Fatalf("expected ErrInternal, got %v", err)
	}
}

// TestDistanceSetFieldMissingFromTelemetry checks that if the setpoint
// requests a sub-field the current telemetry doesn't have, getDistance
// reports an internal error rather than silently ignoring it.
func TestDistanceSetFieldMissingFromTelemetry(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Altitude: f32(10)}.Build()
	telemetry := telemetryGlobal(commonpb.GlobalPosition_builder{Latitude: f64(0)}.Build()) // no altitude

	_, _, err := getDistance(setpoint, telemetry, opt.Tolerances{PosTol: 1})
	if !errors.Is(err, ErrInternal) {
		t.Fatalf("expected ErrInternal, got %v", err)
	}
}

// TestDistanceOnlyComparesSetSubfields checks that unset setpoint
// sub-fields are skipped rather than compared, even when the telemetry
// doesn't have a value for them either.
func TestDistanceOnlyComparesSetSubfields(t *testing.T) {
	setpoint := commonpb.RelativePosition_builder{X: f32(5)}.Build() // only X set
	telemetry := telemetryRelative(commonpb.RelativePosition_builder{X: f32(5)}.Build())

	dist, ok, err := getDistance(setpoint, telemetry, opt.Tolerances{PosTol: 1})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok || dist != 0 {
		t.Errorf("expected exact match on the only compared field, got dist=%v ok=%v", dist, ok)
	}
}

// TestDistanceZeroToleranceRequiresExactMatch checks the distAcc
// zero-tolerance behavior end to end: a zero tolerance means any nonzero
// difference fails with an infinite normalized distance.
func TestDistanceZeroToleranceRequiresExactMatch(t *testing.T) {
	setpoint := commonpb.RelativePosition_builder{X: f32(5)}.Build()
	tol := opt.Tolerances{PosTol: 0}

	exact := telemetryRelative(commonpb.RelativePosition_builder{X: f32(5)}.Build())
	dist, ok, err := getDistance(setpoint, exact, tol)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok || dist != 0 {
		t.Errorf("expected exact match to pass with dist=0, got dist=%v ok=%v", dist, ok)
	}

	mismatch := telemetryRelative(commonpb.RelativePosition_builder{X: f32(5.001)}.Build())
	dist, ok, err = getDistance(setpoint, mismatch, tol)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ok {
		t.Errorf("expected mismatch under zero tolerance to fail")
	}
	if !math.IsInf(float64(dist), 1) {
		t.Errorf("expected infinite normalized distance, got %v", dist)
	}
}
