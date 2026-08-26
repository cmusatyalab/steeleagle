package sdk

import (
	"context"

	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// Vehicle is the interface that all SDK code interacts with. It provides
// wrappers over SteelEagle API RPC calls, and provides waiter objects that
// can wait for the command to complete. This interface can be selectively
// masked out when drivers do not support certain RPC methods.
type Vehicle interface {
	Ctx() context.Context // retrieves the current context
	// #exclude-ifndef services/driver/ControlService/TakeOff
	TakeOff(options ...opt.Option[opt.TakeOffOption]) *waiter[TakeOffResponse]
	// #exclude-ifndef services/driver/ControlService/Land
	Land() *waiter[LandResponse]
	// #exclude-ifndef services/driver/ControlService/Hold
	Hold() *waiter[HoldResponse]
	// #exclude-ifndef services/driver/ControlService/Kill
	Kill() *waiter[KillResponse]
	// #exclude-ifndef services/driver/ControlService/ReturnToHome
	ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *waiter[ReturnToHomeResponse]
	// #exclude-ifndef services/driver/ControlService/SetGlobalPositionTarget
	SetGlobalPositionTarget(
		latitude, longitude float64, altitude, heading float32,
		options ...opt.Option[opt.SetGlobalPositionTargetOption],
	) *waiter[SetGlobalPositionTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetRelativePositionTarget
	SetRelativePositionTarget(
		x, y, z, angle float32,
		options ...opt.Option[opt.SetRelativePositionTargetOption],
	) *waiter[SetRelativePositionTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetVelocityTarget
	SetVelocityTarget(
		xVel, yVel, zVel, angularVel float32,
		options ...opt.Option[opt.SetVelocityTargetOption],
	) *waiter[SetVelocityTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetGimbalAngleTarget
	SetGimbalAngleTarget(
		pitch, roll, yaw float32,
		options ...opt.Option[opt.SetGimbalAngleTargetOption],
	) *waiter[SetGimbalAngleTargetResponse]
	// #exclude-ifndef services/driver/ControlService/SetGimbalVelocityTarget
	SetGimbalVelocityTarget(
		pitchVel, rollVel, yawVel float32,
	) *waiter[SetGimbalVelocityTargetResponse]
	// #exclude-ifndef services/driver/StreamService/StreamTelemetry
	GetTelemetry() *waiter[Telemetry]
}
