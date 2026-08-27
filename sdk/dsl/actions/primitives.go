package actions

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// TakeOff orders the vehicle to take off at its current position.
type TakeOff struct {
	// #optional
	Altitude float32
}

func (i *TakeOff) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	options := []opt.Option[opt.TakeOffOption]{}
	// #exclude-ifndef services/driver/TakeOffRequest/altitude
	options = append(options, opt.WithAltitude[opt.TakeOffOption](i.Altitude))
	_, err := v.TakeOff(options...).Wait()
	return err
}

var _ dsl.Action = &TakeOff{}

// Land orders the vehicle to land at its current position.
type Land struct{}

func (i *Land) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	_, err := v.Land().Wait()
	return err
}

var _ dsl.Action = &Land{}

// ReturnToHome orders the vehicle to return to its start position.
type ReturnToHome struct {
	// #optional
	EndBehavior enums.ReturnToHomeEndBehavior
	// #optional
	MinReturnAltitude float32
	// #optional
	FinalAltitude float32
}

func (i *ReturnToHome) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	options := []opt.Option[opt.ReturnToHomeOption]{}
	options = append(options, opt.WithEndBehavior[opt.ReturnToHomeOption](i.EndBehavior))
	// #exclude-ifndef services/driver/ReturnToHomeRequest/min_return_altitude
	options = append(options, opt.WithMinReturnAltitude[opt.ReturnToHomeOption](i.MinReturnAltitude))
	// #exclude-ifndef services/driver/ReturnToHomeRequest/final_altitude
	options = append(options, opt.WithFinalAltitude[opt.ReturnToHomeOption](i.FinalAltitude))
	_, err := v.ReturnToHome(options...).Wait()
	return err
}

var _ dsl.Action = &ReturnToHome{}

// GoToGlobalPosition orders the vehicle to transit to a global
// position.
type GoToGlobalPosition struct {
	Position types.GlobalPosition
	// #optional
	HeadingMode enums.HeadingMode
	// #optional
	AltitudeMode enums.AltitudeMode
	// #optional
	Speed float32
	// #optional
	AngularSpeed float32
}

func (i *GoToGlobalPosition) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	options := []opt.Option[opt.SetGlobalPositionTargetOption]{}
	options = append(options, opt.WithHeadingMode[opt.SetGlobalPositionTargetOption](i.HeadingMode))
	options = append(options, opt.WithAltitudeMode[opt.SetGlobalPositionTargetOption](i.AltitudeMode))
	// #exclude-ifndef services/driver/SetGlobalPositionTargetRequest/speed
	options = append(options, opt.WithSpeed[opt.SetGlobalPositionTargetOption](i.Speed))
	// #exclude-ifndef services/driver/SetGlobalPositionTargetRequest/angular_speed
	options = append(options, opt.WithAngularSpeed[opt.SetGlobalPositionTargetOption](i.AngularSpeed))
	_, err := v.SetGlobalPositionTarget(
        i.Position.Latitude,
        i.Position.Longitude,
        i.Position.Altitude,
        i.Position.Heading,
        options...,
    ).Wait()
	return err
}

var _ dsl.Action = &GoToGlobalPosition{}

// GoToRelativePosition orders the vehicle to transit to a relative
// position.
type GoToRelativePosition struct {
	Position types.RelativePosition
	// #optional
	Speed float32
	// #optional
	AngularSpeed float32
	// #optional
	Frame enums.ReferenceFrame
}

func (i *GoToRelativePosition) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	options := []opt.Option[opt.SetRelativePositionTargetOption]{}
	// #exclude-ifndef services/driver/SetRelativePositionTargetRequest/speed
	options = append(options, opt.WithSpeed[opt.SetRelativePositionTargetOption](i.Speed))
	// #exclude-ifndef services/driver/SetRelativePositionTargetRequest/angular_speed
	options = append(options, opt.WithAngularSpeed[opt.SetRelativePositionTargetOption](i.AngularSpeed))
	options = append(options, opt.WithReferenceFrame[opt.SetRelativePositionTargetOption](i.Frame))
	_, err := v.SetRelativePositionTarget(
        i.Position.X,
        i.Position.Y,
        i.Position.Z,
        i.Position.Angle,
        options...,
    ).Wait()
	return err
}

var _ dsl.Action = &GoToRelativePosition{}

// SetGimbalPose orders the vehicle to set the pose of its primary
// gimbal.
type SetGimbalPose struct {
	Pose types.Pose
	// #optional
	AngleMode enums.AngleMode
	// #optional
	Frame enums.ReferenceFrame
}

func (i *SetGimbalPose) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	options := []opt.Option[opt.SetGimbalAngleTargetOption]{}
	options = append(options, opt.WithAngleMode[opt.SetGimbalAngleTargetOption](i.AngleMode))
	options = append(options, opt.WithReferenceFrame[opt.SetGimbalAngleTargetOption](i.Frame))
	_, err := v.SetGimbalAngleTarget(
        i.Pose.Pitch,
        i.Pose.Roll,
        i.Pose.Yaw,
        options...,
    ).Wait()
	return err
}

var _ dsl.Action = &SetGimbalPose{}
