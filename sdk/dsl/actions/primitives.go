package actions

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

type TakeOff struct {
	Options []opt.Option[opt.TakeOffOption]
}

func (i *TakeOff) Execute(v sdk.Vehicle) error {
	_, err := v.TakeOff(i.Options...).Wait()
	return err
}

type Land struct{}

func (i *Land) Execute(v sdk.Vehicle) error {
	_, err := v.Land().Wait()
	return err
}

type ReturnToHome struct {
	Options []opt.Option[opt.ReturnToHomeOption]
}

func (i *ReturnToHome) Execute(v sdk.Vehicle) error {
	_, err := v.ReturnToHome(i.Options...).Wait()
	return err
}

type GoToGlobalPosition struct {
	Latitude  float64
	Longitude float64
	Altitude  float32
	Heading   float32
	Options   []opt.Option[opt.SetGlobalPositionTargetOption]
}

func (i *GoToGlobalPosition) Execute(v sdk.Vehicle) error {
	_, err := v.SetGlobalPositionTarget(i.Latitude, i.Longitude, i.Altitude, i.Heading, i.Options...).Wait()
	return err
}

type GoToRelativePosition struct {
	X       float32
	Y       float32
	Z       float32
	Angle   float32
	Options []opt.Option[opt.SetRelativePositionTargetOption]
}

func (i *GoToRelativePosition) Execute(v sdk.Vehicle) error {
	_, err := v.SetRelativePositionTarget(i.X, i.Y, i.Z, i.Angle, i.Options...).Wait()
	return err
}

type SetGimbalPose struct {
	Pitch   float32
	Roll    float32
	Yaw     float32
	Options []opt.Option[opt.SetGimbalAngleTargetOption]
}

func (i *SetGimbalPose) Execute(v sdk.Vehicle) error {
	_, err := v.SetGimbalAngleTarget(i.Pitch, i.Roll, i.Yaw, i.Options...).Wait()
	return err
}
