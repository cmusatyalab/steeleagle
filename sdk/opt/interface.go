package opt

import (
	"github.com/cmusatyalab/steeleagle/sdk/types"
)

type TakeOffOption interface {
	SetAltitude(float32)
}

type ReturnToHomeOption interface {
	SetEndBehavior(types.ReturnToHomeEndBehavior)
	SetMinReturnAltitude(float32)
	SetFinalAltitude(float32)
}

type GoToGlobalPositionOption interface {
	SetHeadingMode(types.HeadingMode)
	SetAltitudeMode(types.AltitudeMode)
	SetSpeed(float32)
	SetAngularSpeed(float32)
}

type GoToRelativePositionOption interface {
	SetSpeed(float32)
	SetAngularSpeed(float32)
	SetReferenceFrame(types.ReferenceFrame)
}

type SetVelocityOption interface {
	SetReferenceFrame(types.ReferenceFrame)
}

type SetGimbalPoseOption interface {
	SetPoseMode(types.PoseMode)
	SetReferenceFrame(types.ReferenceFrame)
}
