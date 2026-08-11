package opt

import (
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
)

// Option is the base option type for RPC options.
type Option[T any] func(T)

// TakeOffOption represents an option for a TakeOff RPC.
type TakeOffOption interface {
	SetAltitude(float32)
}

// ReturnToHomeOption represents an option for a ReturnToHome RPC.
type ReturnToHomeOption interface {
	SetEndBehavior(driverpb.ReturnToHomeEndBehavior)
	SetMinReturnAltitude(float32)
	SetFinalAltitude(float32)
}

// SetGlobalPositionTargetOption represents an option for a SetGlobalPositionTarget RPC.
type SetGlobalPositionTargetOption interface {
	SetHeadingMode(driverpb.HeadingMode)
	SetAltitudeMode(driverpb.AltitudeMode)
	SetSpeed(float32)
	SetAngularSpeed(float32)
}

// SetRelativePositionTargetOption represents an option for a SetRelativePositionTarget RPC.
type SetRelativePositionTargetOption interface {
	SetSpeed(float32)
	SetAngularSpeed(float32)
	SetFrame(driverpb.ReferenceFrame)
}

// SetVelocityTargetOption represents an option for a SetVelocityTarget RPC.
type SetVelocityTargetOption interface {
	SetFrame(driverpb.ReferenceFrame)
}

// SetGimbalAngleTargetOption represents an option for a SetGimbalAngleTarget RPC.
type SetGimbalAngleTargetOption interface {
	SetAngleMode(driverpb.AngleMode)
}

// SetGimbalVelocityTargetOption represents an option for a SetGimbalVelocityTarget RPC.
type SetGimbalVelocityTargetOption interface {
	SetFrame(driverpb.ReferenceFrame)
}

// hasAltitude checks that the base interface supports an optional altitude.
type hasAltitude interface {
	SetAltitude(float32)
}

// WithAltitude sets the altitude for a request that supports it.
func WithAltitude[T hasAltitude](altitude float32) func(T) {
	return func(t T) {
		t.SetAltitude(altitude)
	}
}

// hasEndBehavior checks that the base interface supports an optional end behavior.
type hasEndBehavior interface {
	SetEndBehavior(driverpb.ReturnToHomeEndBehavior)
}

// WithEndBehavior sets the end behavior for a request that supports it.
func WithEndBehavior[T hasEndBehavior](endBehavior enums.ReturnToHomeEndBehavior) func(T) {
	return func(t T) {
		t.SetEndBehavior(driverpb.ReturnToHomeEndBehavior(endBehavior))
	}
}

// hasMinReturnAltitude checks that the base interface supports an optional minimum return
// altitude.
type hasMinReturnAltitude interface {
	SetMinReturnAltitude(float32)
}

// WithMinReturnAltitude sets the minimum return altitude for a request that supports it.
func WithMinReturnAltitude[T hasMinReturnAltitude](altitude float32) func(T) {
	return func(t T) {
		t.SetMinReturnAltitude(altitude)
	}
}

// hasFinalAltitude checks that the base interface supports an optional final altitude.
type hasFinalAltitude interface {
	SetFinalAltitude(float32)
}

// WithFinalAltitude sets the final altitude for a request that supports it.
func WithFinalAltitude[T hasFinalAltitude](altitude float32) func(T) {
	return func(t T) {
		t.SetFinalAltitude(altitude)
	}
}

// hasHeadingMode checks that the base interface supports an optional heading mode.
type hasHeadingMode interface {
	SetHeadingMode(driverpb.HeadingMode)
}

// WithHeadingMode sets the heading mode for a request that supports it.
func WithHeadingMode[T hasHeadingMode](mode enums.HeadingMode) func(T) {
	return func(t T) {
		t.SetHeadingMode(driverpb.HeadingMode(mode))
	}
}

// hasAltitudeMode checks that the base interface supports an optional altitude mode.
type hasAltitudeMode interface {
	SetAltitudeMode(driverpb.AltitudeMode)
}

// WithAltitudeMode sets the altitude mode for a request that supports it.
func WithAltitudeMode[T hasAltitudeMode](mode enums.AltitudeMode) func(T) {
	return func(t T) {
		t.SetAltitudeMode(driverpb.AltitudeMode(mode))
	}
}

// hasSpeed checks that the base interface supports an optional speed.
type hasSpeed interface {
	SetSpeed(float32)
}

// WithSpeed sets the speed for a request that supports it.
func WithSpeed[T hasSpeed](speed float32) func(T) {
	return func(t T) {
		t.SetSpeed(speed)
	}
}

// hasAngularSpeed checks that the base interface supports an optional angular speed.
type hasAngularSpeed interface {
	SetAngularSpeed(float32)
}

// WithAngularSpeed sets the angular speed for a request that supports it.
func WithAngularSpeed[T hasAngularSpeed](angularSpeed float32) func(T) {
	return func(t T) {
		t.SetAngularSpeed(angularSpeed)
	}
}

// hasReferenceFrame checks that the base interface supports an optional reference frame.
type hasReferenceFrame interface {
	SetFrame(driverpb.ReferenceFrame)
}

// WithReferenceFrame sets the reference frame for a request that supports it.
func WithReferenceFrame[T hasReferenceFrame](frame enums.ReferenceFrame) func(T) {
	return func(t T) {
		t.SetFrame(driverpb.ReferenceFrame(frame))
	}
}

// hasAngleMode checks that the base interface supports an optional pose mode.
type hasAngleMode interface {
	SetAngleMode(driverpb.AngleMode)
}

// WithAngleMode sets the pose mode for a request that supports it.
func WithAngleMode[T hasAngleMode](mode enums.AngleMode) func(T) {
	return func(t T) {
		t.SetAngleMode(driverpb.AngleMode(mode))
	}
}
