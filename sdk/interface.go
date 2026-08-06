package sdk

import (
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

type Vehicle interface {
	TakeOff(options ...opt.Option[opt.TakeOffOption]) *waiter[TakeOffResponse]
	Land() *waiter[LandResponse]
	Hold() *waiter[HoldResponse]
	Kill() *waiter[KillResponse]
	SetHome(latitude, longitude, altitude float64) *waiter[SetHomeResponse]
	ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *waiter[ReturnToHomeResponse]
	GoToGlobalPosition(
		latitude, longitude, altitude, heading float64,
		options ...opt.Option[opt.GoToGlobalPositionOption],
	) *waiter[GoToGlobalPositionResponse]
	GoToRelativePosition(
		x, y, z, angle float64,
		options ...opt.Option[opt.GoToRelativePositionOption],
	) *waiter[GoToRelativePositionResponse]
	SetVelocity(
		xVel, yVel, zVel, angularVel float64,
		options ...opt.Option[opt.SetVelocityOption],
	) *waiter[SetVelocityResponse]
	SetGimbalPose(
		pitch, roll, yaw float64,
		options ...opt.Option[opt.SetGimbalPoseOption],
	) *waiter[SetGimbalPoseResponse]
	GetTelemetry() *waiter[Telemetry]
}
