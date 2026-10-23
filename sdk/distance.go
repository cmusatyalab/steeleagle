package sdk

import (
	"fmt"
	"math"

	"github.com/rs/zerolog"
	"google.golang.org/protobuf/proto"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/cmusatyalab/steeleagle/sdk/geo"
)

// getDistance finds the distance between the setpoint and the vehicle
// position, and returns a normalized tolerance-check distance. Each set
// sub-field's raw difference divided by its own tolerance, summed across
// every sub-field that was compared, along with the pass/fail result (true
// iff every compared sub-field's normalized distance is <= 1).
func getDistance(log zerolog.Logger, a proto.Message, t *telemetrypb.Telemetry, tol Tolerances) (float32, bool, error) {
	switch sp := a.(type) {
	case *commonpb.GlobalPosition:
		return globalPositionDistance(newDistAcc(log, "global_position"), sp, t, tol)
	case *commonpb.RelativePosition:
		return relativePositionDistance(newDistAcc(log, "relative_position"), sp, t, tol)
	case *commonpb.Velocity:
		return velocityDistance(newDistAcc(log, "velocity"), sp, t, tol)
	case *commonpb.Pose:
		return poseDistance(newDistAcc(log, "pose"), sp, t, tol)
	case *commonpb.PoseVelocity:
		return poseVelocityDistance(newDistAcc(log, "pose_velocity"), sp, t, tol)
	default:
		log.Debug().Str("setpoint", string(proto.MessageName(a))).Msg("no distance for setpoint type")
		return 0, false, ErrInternal
	}
}

// distAcc accumulates the sum of normalized (|raw|/tolerance) distances
// across every sub-field that was actually compared, plus the overall
// pass/fail. Summing (rather than taking the max) ensures that progress on
// any single axis is reflected in the total, so one axis stalling doesn't
// hide convergence on another. Each compared sub-field is logged, along
// with the outcome, in one trace event per distance.
type distAcc struct {
	sum      float32
	ok       bool
	setpoint string
	ev       *zerolog.Event // nil when trace logging is disabled
}

// newDistAcc creates a distAcc for a setpoint of the given kind, logging
// to log.
func newDistAcc(log zerolog.Logger, setpoint string) *distAcc {
	return &distAcc{ok: true, setpoint: setpoint, ev: log.Trace().Str("setpoint", setpoint)}
}

// add folds in one sub-field's raw difference and its tolerance. A
// zero-or-negative tolerance is treated as an exact match. Any
// nonzero difference fails with an infinite normalized distance.
func (d *distAcc) add(field string, raw, tolerance float32) {
	raw = absf32(raw)
	d.ev.Float32(field, raw)
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

// result logs and returns the accumulated distance and pass/fail.
func (d *distAcc) result() (float32, bool, error) {
	d.ev.Float32("distance", d.sum).Bool("within_tolerance", d.ok).Msg("distance to setpoint")
	return d.sum, d.ok, nil
}

// missing logs and returns the error, an ErrInternal naming field, for
// telemetry lacking field, which the setpoint needs to be compared against.
func (d *distAcc) missing(field string) (float32, bool, error) {
	d.ev.Str("missing", field).Msg("telemetry is missing a field the setpoint needs")
	return 0, false, fmt.Errorf("%w: telemetry has no %s for %s setpoint", ErrInternal, field, d.setpoint)
}

// absf32 implements math.Abs for float32 since it would otherwise require
// conversion to float64.
func absf32(v float32) float32 {
	if v < 0 {
		return -v
	}
	return v
}

// globalPositionDistance gets the distance for a GlobalPosition setpoint.
func globalPositionDistance(acc *distAcc, sp *commonpb.GlobalPosition, t *telemetrypb.Telemetry, tol Tolerances) (float32, bool, error) {
	pi := t.GetPositionInfo()
	if pi == nil {
		return acc.missing("position_info")
	}
	gp := pi.GetGlobalPosition()
	if gp == nil {
		return acc.missing("position_info.global_position")
	}

	if sp.HasLatitude() && sp.HasLongitude() {
		if !gp.HasLatitude() || !gp.HasLongitude() {
			return acc.missing("latitude/longitude")
		}
		horiz := float32(geo.DistanceMeters(sp.GetLatitude(), sp.GetLongitude(), gp.GetLatitude(), gp.GetLongitude()))
		acc.add("horizontal", horiz, tol.PosTol)
	}

	if sp.HasAltitude() {
		if !gp.HasAltitude() {
			return acc.missing("altitude")
		}
		acc.add("altitude", sp.GetAltitude()-gp.GetAltitude(), tol.PosTol)
	}

	if sp.HasHeading() {
		if !gp.HasHeading() {
			return acc.missing("heading")
		}
		acc.add("heading", geo.AngleDiff(sp.GetHeading(), gp.GetHeading()), tol.AngleTol)
	}

	return acc.result()
}

// relativePositionDistance gets the distance for a RelativePosition setpoint.
func relativePositionDistance(acc *distAcc, sp *commonpb.RelativePosition, t *telemetrypb.Telemetry, tol Tolerances) (float32, bool, error) {
	pi := t.GetPositionInfo()
	if pi == nil {
		return acc.missing("position_info")
	}
	rp := pi.GetRelativePosition()
	if rp == nil {
		return acc.missing("position_info.relative_position")
	}

	if sp.HasX() {
		if !rp.HasX() {
			return acc.missing("x")
		}
		acc.add("x", sp.GetX()-rp.GetX(), tol.PosTol)
	}
	if sp.HasY() {
		if !rp.HasY() {
			return acc.missing("y")
		}
		acc.add("y", sp.GetY()-rp.GetY(), tol.PosTol)
	}
	if sp.HasZ() {
		if !rp.HasZ() {
			return acc.missing("z")
		}
		acc.add("z", sp.GetZ()-rp.GetZ(), tol.PosTol)
	}
	if sp.HasAngle() {
		if !rp.HasAngle() {
			return acc.missing("angle")
		}
		acc.add("angle", geo.AngleDiff(sp.GetAngle(), rp.GetAngle()), tol.AngleTol)
	}

	return acc.result()
}

// velocityDistance gets the distance for a Velocity setpoint.
func velocityDistance(acc *distAcc, sp *commonpb.Velocity, t *telemetrypb.Telemetry, tol Tolerances) (float32, bool, error) {
	pi := t.GetPositionInfo()
	if pi == nil {
		return acc.missing("position_info")
	}
	v := pi.GetVelocityNeu()
	if v == nil {
		return acc.missing("position_info.velocity_neu")
	}

	if sp.HasXVel() {
		if !v.HasXVel() {
			return acc.missing("x_vel")
		}
		acc.add("x_vel", sp.GetXVel()-v.GetXVel(), tol.SpeedTol)
	}
	if sp.HasYVel() {
		if !v.HasYVel() {
			return acc.missing("y_vel")
		}
		acc.add("y_vel", sp.GetYVel()-v.GetYVel(), tol.SpeedTol)
	}
	if sp.HasZVel() {
		if !v.HasZVel() {
			return acc.missing("z_vel")
		}
		acc.add("z_vel", sp.GetZVel()-v.GetZVel(), tol.SpeedTol)
	}
	if sp.HasAngularVel() {
		if !v.HasAngularVel() {
			return acc.missing("angular_vel")
		}
		acc.add("angular_vel", sp.GetAngularVel()-v.GetAngularVel(), tol.AngSpeedTol)
	}

	return acc.result()
}

// poseDistance gets the distance for a Pose setpoint.
func poseDistance(acc *distAcc, sp *commonpb.Pose, t *telemetrypb.Telemetry, tol Tolerances) (float32, bool, error) {
	gi := t.GetGimbalInfo()
	if gi == nil {
		return acc.missing("gimbal_info")
	}
	p := gi.GetPoseNeu()
	if p == nil {
		return acc.missing("gimbal_info.pose_neu")
	}

	if sp.HasPitch() {
		if !p.HasPitch() {
			return acc.missing("pitch")
		}
		acc.add("pitch", geo.AngleDiff(sp.GetPitch(), p.GetPitch()), tol.AngleTol)
	}
	if sp.HasRoll() {
		if !p.HasRoll() {
			return acc.missing("roll")
		}
		acc.add("roll", geo.AngleDiff(sp.GetRoll(), p.GetRoll()), tol.AngleTol)
	}
	if sp.HasYaw() {
		if !p.HasYaw() {
			return acc.missing("yaw")
		}
		acc.add("yaw", geo.AngleDiff(sp.GetYaw(), p.GetYaw()), tol.AngleTol)
	}

	return acc.result()
}

// poseVelocityDistance gets the distance for a PoseVelocity setpoint.
func poseVelocityDistance(acc *distAcc, sp *commonpb.PoseVelocity, t *telemetrypb.Telemetry, tol Tolerances) (float32, bool, error) {
	gi := t.GetGimbalInfo()
	if gi == nil {
		return acc.missing("gimbal_info")
	}
	pv := gi.GetAngularVelocityNeu()
	if pv == nil {
		return acc.missing("gimbal_info.angular_velocity_neu")
	}

	if sp.HasPitchVel() {
		if !pv.HasPitchVel() {
			return acc.missing("pitch_vel")
		}
		acc.add("pitch_vel", sp.GetPitchVel()-pv.GetPitchVel(), tol.AngSpeedTol)
	}
	if sp.HasRollVel() {
		if !pv.HasRollVel() {
			return acc.missing("roll_vel")
		}
		acc.add("roll_vel", sp.GetRollVel()-pv.GetRollVel(), tol.AngSpeedTol)
	}
	if sp.HasYawVel() {
		if !pv.HasYawVel() {
			return acc.missing("yaw_vel")
		}
		acc.add("yaw_vel", sp.GetYawVel()-pv.GetYawVel(), tol.AngSpeedTol)
	}

	return acc.result()
}
