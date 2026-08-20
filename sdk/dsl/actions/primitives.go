package actions

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// TakeOff orders the vehicle to take off at its current position.
type TakeOff struct {
	Options []opt.Option[opt.TakeOffOption]
}

func (i *TakeOff) Execute(v sdk.Vehicle) error {
	_, err := v.TakeOff(i.Options...).Wait()
	return err
}

var _ dsl.Action = &TakeOff{}

// Land orders the vehicle to land at its current position.
type Land struct{}

func (i *Land) Execute(v sdk.Vehicle) error {
	_, err := v.Land().Wait()
	return err
}

var _ dsl.Action = &Land{}

// ReturnToHome orders the vehicle to return to its start position.
type ReturnToHome struct {
	Options []opt.Option[opt.ReturnToHomeOption]
}

func (i *ReturnToHome) Execute(v sdk.Vehicle) error {
	_, err := v.ReturnToHome(i.Options...).Wait()
	return err
}

var _ dsl.Action = &ReturnToHome{}

// GoToGlobalPosition orders the vehicle to transit to a global
// position.
type GoToGlobalPosition struct {
	types.GlobalPosition
	Options []opt.Option[opt.SetGlobalPositionTargetOption]
}

func (i *GoToGlobalPosition) Execute(v sdk.Vehicle) error {
	_, err := v.SetGlobalPositionTarget(i.Latitude, i.Longitude, i.Altitude, i.Heading, i.Options...).Wait()
	return err
}

var _ dsl.Action = &GoToGlobalPosition{}

// GoToRelativePosition orders the vehicle to transit to a relative
// position.
type GoToRelativePosition struct {
	types.RelativePosition
	Options []opt.Option[opt.SetRelativePositionTargetOption]
}

func (i *GoToRelativePosition) Execute(v sdk.Vehicle) error {
	_, err := v.SetRelativePositionTarget(i.X, i.Y, i.Z, i.Angle, i.Options...).Wait()
	return err
}

var _ dsl.Action = &GoToRelativePosition{}

// SetGimbalPose orders the vehicle to set the pose of its primary
// gimbal.
type SetGimbalPose struct {
	types.Pose
	Options []opt.Option[opt.SetGimbalAngleTargetOption]
}

func (i *SetGimbalPose) Execute(v sdk.Vehicle) error {
	_, err := v.SetGimbalAngleTarget(i.Pitch, i.Roll, i.Yaw, i.Options...).Wait()
	return err
}

var _ dsl.Action = &SetGimbalPose{}
