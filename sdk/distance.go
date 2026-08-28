package sdk

import (
	"math"

	"google.golang.org/protobuf/proto"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// getDistance finds the distance between the setpoint and the vehicle
// position, and returns a normalized tolerance-check distance. Each set
// sub-field's raw difference divided by its own tolerance, summed across
// every sub-field that was compared, along with the pass/fail result (true
// iff every compared sub-field's normalized distance is <= 1).
func getDistance(a proto.Message, t *telemetrypb.Telemetry, tol opt.Tolerances) (float32, bool, error) {
	switch sp := a.(type) {
	case *commonpb.GlobalPosition:
		return globalPositionDistance(sp, t, tol)
	case *commonpb.RelativePosition:
		return relativePositionDistance(sp, t, tol)
	case *commonpb.Velocity:
		return velocityDistance(sp, t, tol)
	case *commonpb.Pose:
		return poseDistance(sp, t, tol)
	case *commonpb.PoseVelocity:
		return poseVelocityDistance(sp, t, tol)
	default:
		return 0, false, ErrInternal
	}
}

// distAcc accumulates the sum of normalized (|raw|/tolerance) distances
// across every sub-field that was actually compared, plus the overall
// pass/fail. Summing (rather than taking the max) ensures that progress on
// any single axis is reflected in the total, so one axis stalling can't
// hide genuine convergence on another.
type distAcc struct {
	sum float32
	ok  bool
}

func newDistAcc() *distAcc {
	return &distAcc{ok: true}
}

// add folds in one sub-field's raw difference and its tolerance. A
// zero-or-negative tolerance is treated as "must match exactly". Any
// nonzero difference fails with an infinite normalized distance, rather
// than silently producing a NaN/Inf that comparisons might mishandle.
func (d *distAcc) add(raw, tolerance float32) {
	raw = absf32(raw)
	if tolerance <= 0 {
		if raw != 0 {
			d.ok = false
			d.sum = float32(math.Inf(1))
		}
		return
	}
	norm := raw / tolerance
	d.sum += norm
	if norm > 1 {
		d.ok = false
	}
}

// absf32 implements math.Abs for float32 since it would otherwise require
// conversion to float64.
func absf32(v float32) float32 {
	if v < 0 {
		return -v
	}
	return v
}

// angularDiff returns the smallest difference between two angles in
// degrees, correctly handling wraparound (e.g. 359 vs 1 is a 2-degree
// difference, not 358).
func angularDiff(a, b float32) float32 {
	d := absf32(a - b)
	if d > 180 {
		d = 360 - d
	}
	return d
}

// haversineMeters returns the great-circle distance in meters between two
// lat/lon points given in degrees.
func haversineMeters(lat1, lon1, lat2, lon2 float64) float32 {
	const earthRadiusM = 6371000.0
	toRad := func(deg float64) float64 { return deg * math.Pi / 180 }
	dLat := toRad(lat2 - lat1)
	dLon := toRad(lon2 - lon1)
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(toRad(lat1))*math.Cos(toRad(lat2))*math.Sin(dLon/2)*math.Sin(dLon/2)
	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
	return float32(earthRadiusM * c)
}

// globalPositionDistance gets the distance for a GlobalPosition setpoint.
func globalPositionDistance(sp *commonpb.GlobalPosition, t *telemetrypb.Telemetry, tol opt.Tolerances) (float32, bool, error) {
	pi := t.GetPositionInfo()
	if pi == nil {
		return 0, false, ErrInternal
	}
	gp := pi.GetGlobalPosition()
	if gp == nil {
		return 0, false, ErrInternal
	}

	acc := newDistAcc()

	if sp.HasLatitude() && sp.HasLongitude() {
		if !gp.HasLatitude() || !gp.HasLongitude() {
			return 0, false, ErrInternal
		}
		horiz := haversineMeters(sp.GetLatitude(), sp.GetLongitude(), gp.GetLatitude(), gp.GetLongitude())
		acc.add(horiz, tol.PosTol)
	}

	if sp.HasAltitude() {
		if !gp.HasAltitude() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetAltitude()-gp.GetAltitude(), tol.PosTol)
	}

	if sp.HasHeading() {
		if !gp.HasHeading() {
			return 0, false, ErrInternal
		}
		acc.add(angularDiff(sp.GetHeading(), gp.GetHeading()), tol.AngleTol)
	}

	return acc.sum, acc.ok, nil
}

// relativePositionDistance gets the distance for a RelativePosition setpoint.
func relativePositionDistance(sp *commonpb.RelativePosition, t *telemetrypb.Telemetry, tol opt.Tolerances) (float32, bool, error) {
	pi := t.GetPositionInfo()
	if pi == nil {
		return 0, false, ErrInternal
	}
	rp := pi.GetRelativePosition()
	if rp == nil {
		return 0, false, ErrInternal
	}

	acc := newDistAcc()

	if sp.HasX() {
		if !rp.HasX() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetX()-rp.GetX(), tol.PosTol)
	}
	if sp.HasY() {
		if !rp.HasY() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetY()-rp.GetY(), tol.PosTol)
	}
	if sp.HasZ() {
		if !rp.HasZ() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetZ()-rp.GetZ(), tol.PosTol)
	}
	if sp.HasAngle() {
		if !rp.HasAngle() {
			return 0, false, ErrInternal
		}
		acc.add(angularDiff(sp.GetAngle(), rp.GetAngle()), tol.AngleTol)
	}

	return acc.sum, acc.ok, nil
}

// velocityDistance gets the distance for a Velocity setpoint.
func velocityDistance(sp *commonpb.Velocity, t *telemetrypb.Telemetry, tol opt.Tolerances) (float32, bool, error) {
	pi := t.GetPositionInfo()
	if pi == nil {
		return 0, false, ErrInternal
	}
	v := pi.GetVelocityNeu()
	if v == nil {
		return 0, false, ErrInternal
	}

	acc := newDistAcc()

	if sp.HasXVel() {
		if !v.HasXVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetXVel()-v.GetXVel(), tol.SpeedTol)
	}
	if sp.HasYVel() {
		if !v.HasYVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetYVel()-v.GetYVel(), tol.SpeedTol)
	}
	if sp.HasZVel() {
		if !v.HasZVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetZVel()-v.GetZVel(), tol.SpeedTol)
	}
	if sp.HasAngularVel() {
		if !v.HasAngularVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetAngularVel()-v.GetAngularVel(), tol.AngSpeedTol)
	}

	return acc.sum, acc.ok, nil
}

// poseDistance gets the distance for a Pose setpoint.
func poseDistance(sp *commonpb.Pose, t *telemetrypb.Telemetry, tol opt.Tolerances) (float32, bool, error) {
	gi := t.GetGimbalInfo()
	if gi == nil {
		return 0, false, ErrInternal
	}
	p := gi.GetPoseNeu()
	if p == nil {
		return 0, false, ErrInternal
	}

	acc := newDistAcc()

	if sp.HasPitch() {
		if !p.HasPitch() {
			return 0, false, ErrInternal
		}
		acc.add(angularDiff(sp.GetPitch(), p.GetPitch()), tol.AngleTol)
	}
	if sp.HasRoll() {
		if !p.HasRoll() {
			return 0, false, ErrInternal
		}
		acc.add(angularDiff(sp.GetRoll(), p.GetRoll()), tol.AngleTol)
	}
	if sp.HasYaw() {
		if !p.HasYaw() {
			return 0, false, ErrInternal
		}
		acc.add(angularDiff(sp.GetYaw(), p.GetYaw()), tol.AngleTol)
	}

	return acc.sum, acc.ok, nil
}

// poseVelocityDistance gets the distance for a PoseVelocity setpoint.
func poseVelocityDistance(sp *commonpb.PoseVelocity, t *telemetrypb.Telemetry, tol opt.Tolerances) (float32, bool, error) {
	gi := t.GetGimbalInfo()
	if gi == nil {
		return 0, false, ErrInternal
	}
	pv := gi.GetAngularVelocityNeu()
	if pv == nil {
		return 0, false, ErrInternal
	}

	acc := newDistAcc()

	if sp.HasPitchVel() {
		if !pv.HasPitchVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetPitchVel()-pv.GetPitchVel(), tol.AngSpeedTol)
	}
	if sp.HasRollVel() {
		if !pv.HasRollVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetRollVel()-pv.GetRollVel(), tol.AngSpeedTol)
	}
	if sp.HasYawVel() {
		if !pv.HasYawVel() {
			return 0, false, ErrInternal
		}
		acc.add(sp.GetYawVel()-pv.GetYawVel(), tol.AngSpeedTol)
	}

	return acc.sum, acc.ok, nil
}
