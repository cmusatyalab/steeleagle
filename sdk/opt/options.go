package opt

import (
	"github.com/cmusatyalab/steeleagle/sdk/types"
)

type Option[T any] func(T)

type hasAltitude interface {
	SetAltitude(float32)
}

func WithAltitude[T hasAltitude](altitude float32) func(T) {
	return func(t T) {
		t.SetAltitude(altitude)
	}
}

type hasEndBehavior interface {
	SetEndBehavior(types.ReturnToHomeEndBehavior)
}

func WithEndBehavior[T hasEndBehavior](endBehavior types.ReturnToHomeEndBehavior) func(T) {
	return func(t T) {
		t.SetEndBehavior(int32(endBehavior))
	}
}

type hasMinReturnAltitude interface {
	SetMinReturnAltitude(float32)
}

func WithMinReturnAltitude[T hasMinReturnAltitude](altitude float32) func(T) {
	return func(t T) {
		t.SetMinReturnAltitude(altitude)
	}
}

type hasFinalAltitude interface {
	SetFinalAltitude(float32)
}

func WithFinalAltitude[T hasFinalAltitude](altitude float32) func(T) {
	return func(t T) {
		t.SetFinalAltitude(altitude)
	}
}

type hasHeadingMode interface {
	SetHeadingMode(types.HeadingMode)
}

func WithHeadingMode[T hasHeadingMode](mode types.HeadingMode) func(T) {
	return func(t T) {
		t.SetHeadingMode(int32(mode))
	}
}

type hasAltitudeMode interface {
	SetAltitudeMode(types.AltitudeMode)
}

func WithAltitudeMode[T hasAltitudeMode](mode types.AltitudeMode) func(T) {
	return func(t T) {
		t.SetAltitudeMode(int32(mode))
	}
}

type hasSpeed interface {
	SetSpeed(float32)
}

func WithSpeed[T hasSpeed](speed float32) func(T) {
	return func(t T) {
		t.SetSpeed(speed)
	}
}

type hasAngularSpeed interface {
	SetAngularSpeed(float32)
}

func WithAngularSpeed[T hasAngularSpeed](angularSpeed float32) func(T) {
	return func(t T) {
		t.SetAngularSpeed(angularSpeed)
	}
}

type hasReferenceFrame interface {
	SetReferenceFrame(types.ReferenceFrame)
}

func WithReferenceFrame[T hasReferenceFrame](frame types.ReferenceFrame) func(T) {
	return func(t T) {
		t.SetReferenceFrame(int32(frame))
	}
}

type hasPoseMode interface {
	SetPoseMode(types.PoseMode)
}

func WithPoseMode[T hasPoseMode](mode types.PoseMode) func(T) {
	return func(t T) {
		t.SetPoseMode(int32(mode))
	}
}
