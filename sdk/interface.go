//go:build ignore

package sdk

import (
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

type Vehicle interface {
	TakeOff(options ...opt.Option[opt.TakeOffOption]) *waiter[TakeOffResponse]
	Land() *waiter[LandResponse]
	Hold() *waiter[HoldResponse]
	Kill() *waiter[KillResponse]
	ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *waiter[ReturnToHomeResponse]
	SetGlobalPositionTarget(
		latitude, longitude, altitude, heading float64,
		options ...opt.Option[opt.SetGlobalPositionTargetOption],
	) *waiter[SetGlobalPositionTargetResponse]
	SetRelativePositionTarget(
		x, y, z, angle float64,
		options ...opt.Option[opt.SetRelativePositionTargetOption],
	) *waiter[SetRelativePositionResponse]
	SetVelocityTarget(
		xVel, yVel, zVel, angularVel float64,
		options ...opt.Option[opt.SetVelocityTargetOption],
	) *waiter[SetVelocityTargetResponse]
	SetGimbalAngleTarget(
		pitch, roll, yaw float64,
		options ...opt.Option[opt.SetGimbalAngleTargetOption],
	) *waiter[SetGimbalAngleTargetResponse]
	SetGimbalVelocityTarget(
		pitchVel, rollVel, yawVel float64,
		options ...opt.Option[opt.SetGimbalVelocityTargetOption],
	) *waiter[SetGimbalVelocityTargetResponse]
	GetTelemetry() *waiter[Telemetry]
}
