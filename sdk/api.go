package sdk

import (
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// Vehicle is the interface that all SDK code interacts with. It provides
// wrappers over SteelEagle API RPC calls, and provides waiter objects that
// can wait for the command to complete. This interface can be selectively
// masked out when drivers do not support certain RPC methods.
type Vehicle interface {
	TakeOff(options ...opt.Option[opt.TakeOffOption]) *waiter[TakeOffResponse]
	Land() *waiter[LandResponse]
	Hold() *waiter[HoldResponse]
	Kill() *waiter[KillResponse]
	ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *waiter[ReturnToHomeResponse]
	SetGlobalPositionTarget(
		latitude, longitude float64, altitude, heading float32,
		options ...opt.Option[opt.SetGlobalPositionTargetOption],
	) *waiter[SetGlobalPositionTargetResponse]
	SetRelativePositionTarget(
		x, y, z, angle float32,
		options ...opt.Option[opt.SetRelativePositionTargetOption],
	) *waiter[SetRelativePositionTargetResponse]
	SetVelocityTarget(
		xVel, yVel, zVel, angularVel float32,
		options ...opt.Option[opt.SetVelocityTargetOption],
	) *waiter[SetVelocityTargetResponse]
	SetGimbalAngleTarget(
		pitch, roll, yaw float32,
		options ...opt.Option[opt.SetGimbalAngleTargetOption],
	) *waiter[SetGimbalAngleTargetResponse]
	SetGimbalVelocityTarget(
		pitchVel, rollVel, yawVel float32,
		options ...opt.Option[opt.SetGimbalVelocityTargetOption],
	) *waiter[SetGimbalVelocityTargetResponse]
	GetTelemetry() *waiter[Telemetry]
}
