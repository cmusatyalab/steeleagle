package sdk

import (
	"context"

	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// Vehicle is the interface that all SDK code interacts with. It provides
// wrappers over SteelEagle API RPC calls, and provides Waiter objects that
// can wait for the command to complete. This interface can be selectively
// masked out when drivers do not support certain RPC methods.
type Vehicle interface {
	Ctx() context.Context // retrieves the current context
	// #exclude-ifndef services/driver/ControlService/TakeOff
	TakeOff(options ...opt.Option[opt.TakeOffOption]) *Waiter[TakeOffResponse]
	// #exclude-ifndef services/driver/ControlService/Land
	Land() *Waiter[LandResponse]
	// #exclude-ifndef services/driver/ControlService/Hold
	Hold() *Waiter[HoldResponse]
	// #exclude-ifndef services/driver/ControlService/Kill
	Kill() *Waiter[KillResponse]
	// #exclude-ifndef services/driver/ControlService/ReturnToHome
	ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *Waiter[ReturnToHomeResponse]
	// #exclude-ifndef services/driver/ControlService/SetGlobalPositionTarget
	SetGlobalPositionTarget(
		latitude, longitude float64, altitude, heading float32,
		options ...opt.Option[opt.SetGlobalPositionTargetOption],
	) *Waiter[SetGlobalPositionTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetRelativePositionTarget
	SetRelativePositionTarget(
		x, y, z, angle float32,
		options ...opt.Option[opt.SetRelativePositionTargetOption],
	) *Waiter[SetRelativePositionTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetVelocityTarget
	SetVelocityTarget(
		xVel, yVel, zVel, angularVel float32,
		options ...opt.Option[opt.SetVelocityTargetOption],
	) *Waiter[SetVelocityTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetGimbalAngleTarget
	SetGimbalAngleTarget(
		pitch, roll, yaw float32,
		options ...opt.Option[opt.SetGimbalAngleTargetOption],
	) *Waiter[SetGimbalAngleTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetGimbalVelocityTarget
	SetGimbalVelocityTarget(
		pitchVel, rollVel, yawVel float32,
	) *Waiter[SetGimbalVelocityTargetResponse]
	// #exclude-ifndef services/driver/StreamService/StreamTelemetry
	GetTelemetry() *Waiter[Telemetry]
}
