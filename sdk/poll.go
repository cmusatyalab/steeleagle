//go:build ignore

package sdk

import (
	"math"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
)

// pollFunc checks the current status of an operation. It should return
// true along with the error once the operation has finished.
type pollFunc func(t opt.Tolerances) (bool, error)

// checkFunc verifies that the setpoint carried by a request was actually
// reached once the vehicle has reached its target motion status.
type checkFunc func(*telemetrypb.Telemetry, proto.Message, opt.Tolerances) (bool, error)

// fetchTelemetry retrieves the latest telemetry snapshot for v, translating
// gRPC and missing-payload failures into ErrInternal.
func fetchTelemetry(v *vehicleContext) (*telemetrypb.Telemetry, error) {
	resp, err := v.data.GetTelemetry(v.ctx, &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		return nil, ErrInternal
	}
	if !resp.HasTelemetry() {
		return nil, ErrInternal
	}
	return resp.GetTelemetry(), nil
}

// checkSetpoint confirms that the vehicle's currently tracked setpoint in
// telemetry is still req.
func checkSetpoint(p *telemetrypb.PositionInfo, req proto.Message) error {
	if !p.HasSetpoint() {
		return ErrInternal
	}
	matches, err := anyMatches(p.GetSetpoint(), req)
	if err != nil {
		return ErrInternal
	}
	if !matches {
		return ErrCancelled
	}
	return nil
}

// basePoller is the base poll function for movement based RPCs like GoToGlobalPosition
// or SetVelocity. It waits for the vehicle to achieve a target MotionStatus before
// checking for command expectation.
func basePoller(v *vehicleContext, req proto.Message, target enums.PositionInfo_MotionStatus) pollFunc {
	checker, ok := checkerFor(req)
	if !ok {
		panic("couldn't find checker for request type!")
	}
	return func(tol opt.Tolerances) (bool, error) {
		t, err := fetchTelemetry(v)
		if err != nil {
			return false, err
		}
		if !t.HasPositionInfo() {
			return false, ErrInternal
		}
		p := t.GetPositionInfo()
		if err := checkSetpoint(p, req); err != nil {
			return true, err
		}
		status := enums.PositionInfo_MotionStatus(p.GetMotionStatus())
		if status == target {
			return checker(t, req, tol) // check now since we have hit our target status
		} else if status == enums.PositionInfo_MotionStatusHolding ||
			status == enums.PositionInfo_MotionStatusStopped {
			// If holding/stopping wasn't our target status but we aren't moving, then something
			// has likely gone wrong
			return false, ErrInternal
		}
		return false, nil // go to next iteration
	}
}

// checkerFor selects the checkFunc responsible for verifying the setpoint of
// req once the vehicle has stopped moving.
func checkerFor(req proto.Message) (checkFunc, bool) {
	switch req.(type) {
	case *driverpb.TakeOffRequest:
		return takeOffChecker, true
	case *driverpb.LandRequest:
		return passthroughChecker, true
	case *driverpb.HoldRequest:
		return passthroughChecker, true
	case *driverpb.KillRequest:
		return passthroughChecker, true
	case *driverpb.ReturnToHomeRequest:
		return returnToHomeChecker, true
	case *driverpb.GoToGlobalPositionRequest:
		return goToGlobalPositionChecker, true
	case *driverpb.GoToRelativePositionRequest:
		return goToRelativePositionChecker, true
	case *driverpb.SetVelocityRequest:
		return setVelocityChecker, true
	default:
		return nil, false
	}
}

// takeOffChecker verifies that the vehicle reached the commanded take off
// altitude. basePoller guarantees PositionInfo is present before calling it.
func takeOffChecker(t *telemetrypb.Telemetry, m proto.Message, tol opt.Tolerances) (bool, error) {
	req, ok := m.(*driverpb.TakeOffRequest)
	if !ok {
		panic("couldn't get request from argument")
	}
	if req.HasAltitude() { // only check altitude expectation if it was provided in the request
		p := t.GetPositionInfo()
		if !p.HasRelativePosition() || !p.GetRelativePosition().HasZ() {
			return true, ErrCannotVerify
		}
		if math.Abs(float64(req.GetAltitude())-p.GetRelativePosition().GetZ()) > tol.PosTol {
			return true, ErrFailedExpectation
		} else {
			return true, nil
		}
	}
	return true, nil
}

// passthroughChecker is for checkers that need no verification beyond motion status.
func passthroughChecker(t *telemetrypb.Telemetry, m proto.Message, tol opt.Tolerances) (bool, error) {
	return true, nil
}

// returnToHomeChecker verifies that the vehicle arrived at its home position
// and, depending on the requested end behavior, either landed or is holding
// at the requested final altitude.
func returnToHomeChecker(t *telemetrypb.Telemetry, m proto.Message, tol opt.Tolerances) (bool, error) {
	req, ok := m.(*driverpb.ReturnToHomeRequest)
	if !ok {
		panic("couldn't get request from argument")
	}
	p := t.GetPositionInfo()
	if !p.HasGlobalPosition() || !p.HasHome() {
		return true, ErrCannotVerify
	}
	cur, home := p.GetGlobalPosition(), p.GetHome()
	if cur.HasLatitude() && cur.HasLongitude() && home.HasLatitude() && home.HasLongitude() {
		if haversineMeters(cur.GetLatitude(), cur.GetLongitude(), home.GetLatitude(), home.GetLongitude()) > tol.PosTol {
			return true, ErrFailedExpectation
		}
	} else {
		return true, ErrCannotVerify
	}
	if req.HasFinalAltitude() && req.HasEndBehavior() && req.GetEndBehavior <= 1 { // hover end behavior
		if !p.HasRelativePosition() || !p.GetRelativePosition().HasZ() {
			return true, ErrCannotVerify
		}
		if math.Abs(req.GetFinalAltitude()-p.GetRelativePosition().GetZ()) > tol.PosTol {
			return true, ErrFailedExpectation
		}
	}
	return true, nil
}

// goToGlobalPositionChecker verifies that the vehicle arrived at the
// commanded global position, honoring the requested altitude mode.
func goToGlobalPositionChecker(t *telemetrypb.Telemetry, m proto.Message, tol opt.Tolerances) (bool, error) {
	req, ok := m.(*driverpb.GoToGlobalPositionRequest)
	if !ok || !req.HasPosition() {
		panic("couldn't get request from argument, and request does not contain a position")
	}
	p := t.GetPositionInfo()
	if !p.HasGlobalPosition() {
		return true, ErrCannotVerify
	}
	target := req.GetPosition()
	cur := p.GetGlobalPosition()
	if cur.HasLatitude() && cur.HasLongitude() && target.HasLatitude() && target.HasLongitude() {
		if haversineMeters(cur.GetLatitude(), cur.GetLongitude(), target.GetLatitude(), target.GetLongitude()) > tol.PosTol {
			return true, ErrFailedExpectation
		}
	}
	if req.GetAltitudeMode() <= 1 {
		if p.HasRelativePosition() {
			if r := p.GetRelativePosition(); r.HasZ() && math.Abs(target.GetAltitude()-r.GetZ()) > tol.PosTol {
				return true, ErrFailedExpectation
			}
		} else {
			return true, ErrCannotVerify
		}
	} else if cur.HasAltitude() && math.Abs(target.GetAltitude()-cur.GetAltitude()) > tol.PosTol {
		return true, ErrFailedExpectation
	} else {
		return true, ErrCannotVerify
	}
}

// goToRelativePositionChecker verifies that the vehicle arrived at the
// commanded relative position. This can only be checked for the NEU frame.
func goToRelativePositionChecker(t *telemetrypb.Telemetry, m proto.Message, tol opt.Tolerances) (bool, error) {
	req, ok := m.(*driverpb.GoToRelativePositionRequest)
	if !ok || !req.HasPosition() {
		panic("couldn't get request from argument, and request does not contain a position")
	}
	if req.HasFrame() && req.GetFrame() <= 1 {
		return true, nil // we can't verify a body relative position request
	}
	p := t.GetPositionInfo()
	if !p.HasRelativePosition() {
		return false, ErrCannotVerify
	}
	target := req.GetPosition()
	r := p.GetRelativePosition()
	return true, satisfies(target, r, []float32{tol.PosTol, tol.PosTol, tol.PosTol, tol.AngTol})
}

// setVelocityChecker reports the command complete once the vehicle's
// reported velocity matches the requested setpoint. If the vehicle stops
// moving before converging on the setpoint, it will never get there on its
// own, so that is reported as a failed expectation instead of polling forever.
func setVelocityChecker(t *telemetrypb.Telemetry, m proto.Message, tol opt.Tolerances) (bool, error) {
	req, ok := m.(*driverpb.SetVelocityRequest)
	if !ok || !req.HasVelocity() {
		panic("couldn't get request from argument, and request does not contain a velocity")
	}
	p := t.GetPositionInfo()
	neu := req.HasFrame() && req.GetFrame() == driverpb.ReferenceFrame_REFERENCE_FRAME_NEU
	var cur *commonpb.Velocity
	if neu {
		if !p.HasVelocityNeu() {
			return false, ErrCannotVerify
		}
		cur = p.GetVelocityNeu()
	} else {
		if !p.HasVelocityBody() {
			return false, ErrCannotVerify
		}
		cur = p.GetVelocityBody()
	}
	target := req.GetVelocity()
	if satisfies(cur, target, []float32[tol.SpeedTol, tol.SpeedTol, tol.SpeedTol, tol.AngSpeedTol]) {
		return true, ErrFailedExpectation
	}
	return false, nil
}

// setHomePoller polls telemetry until the reported home position matches the
// one that was requested. Setting home does not move the vehicle, so there
// is no motion status to wait on.
func setHomePoller(v *vehicleContext, req *driverpb.SetHomeRequest, tol opt.Tolerances) pollFunc {
	return func() (bool, error) {
		t, err := fetchTelemetry(v)
		if err != nil {
			return false, err
		}
		if !req.HasNewHome() {
			panic("request does not contain a position")
		}
		if !t.HasPositionInfo() || !t.GetPositionInfo().HasHome() {
			return false, ErrInternal
		}
		home, target := t.GetPositionInfo().GetHome(), req.GetNewHome()
		if home.HasLatitude() && home.HasLongitude() && target.HasLatitude() && target.HasLongitude() {
			if haversineMeters(home.GetLatitude(), home.GetLongitude(), target.GetLatitude(), target.GetLongitude()) > tol.PosTol {
				return false, nil
			}
		}
		return true, nil
	}
}

// setGimbalPosePoller polls telemetry until the gimbal identified by
// req.GimbalId stops moving, then verifies (for absolute pose commands) that
// it reached the requested pose.
func setGimbalPosePoller(v *vehicleContext, req *driverpb.SetGimbalPoseRequest) pollFunc {
	return func() (bool, error) {
		t, err := fetchTelemetry(v)
		if err != nil {
			return false, err
		}
		if !t.HasGimbalInfo() {
			return false, ErrCannotVerify
		}
		return setGimbalPoseChecker(t, req)
	}
}

// setGimbalPoseChecker uses the gimbal's angular velocity as the analog of motion status,
// using it to verify against absolute angle and velocity. Offset is not possible to verify
// against, and is therefore
func setGimbalPoseChecker(t *telemetrypb.Telemetry, m proto.Message) (bool, error) {
	req, ok := m.(*driverpb.SetGimbalPoseRequest)
	if !ok || !req.HasPose() {
		return true, ErrInternal
	}
	var status *telemetrypb.GimbalStatus
	for _, g := range t.GetGimbalInfo().GetGimbals() {
		if g.GetId() == req.GetGimbalId() {
			status = g
			break
		}
	}
	if status == nil {
		return false, ErrInternal
	}
	neu := req.HasFrame() && req.GetFrame() == driverpb.ReferenceFrame_REFERENCE_FRAME_NEU
	var pose, rate *commonpb.Pose
	if neu {
		if !status.HasPoseNeu() || !status.HasAngularVelocityNeu() {
			return false, ErrInternal
		}
		pose, rate = status.GetPoseNeu(), status.GetAngularVelocityNeu()
	} else {
		if !status.HasPoseBody() || !status.HasAngularVelocityBody() {
			return false, ErrInternal
		}
		pose, rate = status.GetPoseBody(), status.GetAngularVelocityBody()
	}
	moving := (rate.HasPitch() && math.Abs(rate.GetPitch()) > angularSpeedTolerance) ||
		(rate.HasRoll() && math.Abs(rate.GetRoll()) > angularSpeedTolerance) ||
		(rate.HasYaw() && math.Abs(rate.GetYaw()) > angularSpeedTolerance)
	if moving {
		return false, nil
	}
	if req.HasPoseMode() && req.GetPoseMode() != driverpb.PoseMode_POSE_MODE_ANGLE {
		return true, nil
	}
	target := req.GetPose()
	if pose.HasPitch() && target.HasPitch() && math.Abs(pose.GetPitch()-target.GetPitch()) > angleTolerance {
		return true, ErrFailedExpectation
	}
	if pose.HasRoll() && target.HasRoll() && math.Abs(pose.GetRoll()-target.GetRoll()) > angleTolerance {
		return true, ErrFailedExpectation
	}
	if pose.HasYaw() && target.HasYaw() && math.Abs(pose.GetYaw()-target.GetYaw()) > angleTolerance {
		return true, ErrFailedExpectation
	}
	return true, nil
}

// satisfies reports whether every field set on a is present on b with an
// equal value according to the equivalent indexed tolerance. If fields
// are not set, it returns ErrCannotVerify, but if they are and not within,
// tolerance, it returns ErrFailedExpectation.
func satisfies(a, b protoreflect.Message, tol []float32) error {
	notVerify := false
	failedExp := false
	fields := a.Descriptor().Fields()
	for i := 0; i < fields.Len(); i++ {
		fd := fields.Get(i)
		if !a.Has(fd) {
			continue
		}
		if !b.Has(fd) {
			notVerify = true
		}
		tol := 0.0 // default to zero tolerance
		index = min(i, len(tol)-1)
		if index >= 0 {
			tol = tol[index]
		}
		if math.Abs(a.Get(fd)-b.Get(fd)) > tol {
			failedExp = true
		}
	}
	if !notVerify && !failedExp {
		return nil
	} else {
		if failedExp {
			return ErrFailedExpectation
		} else {
			return ErrCannotVerify
		}
	}
}

// haversineMeters computes the great-circle distance in meters between two
// latitude/longitude pairs given in degrees.
func haversineMeters(lat1, lon1, lat2, lon2 float64) float64 {
	const earthRadiusMeters = 6371000.0
	toRad := func(deg float64) float64 { return deg * math.Pi / 180 }
	dLat := toRad(lat2 - lat1)
	dLon := toRad(lon2 - lon1)
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(toRad(lat1))*math.Cos(toRad(lat2))*math.Sin(dLon/2)*math.Sin(dLon/2)
	return earthRadiusMeters * 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
}
