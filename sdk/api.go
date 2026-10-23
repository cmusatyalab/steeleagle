package sdk

import (
	"context"

	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// Vehicle is the interface that all SDK code interacts with. It provides
// wrappers over SteelEagle API RPC calls, and provides Waiter objects that
// can wait for the command to complete. This interface can be selectively
// masked out when drivers do not support certain RPC methods.
type Vehicle interface {
	Ctx() context.Context // retrieves the current context
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/TakeOff
	TakeOff(options ...opt.Option[opt.TakeOffOption]) *Waiter[TakeOffResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/Land
	Land() *Waiter[LandResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/Stand
	Stand() *Waiter[StandResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/Sit
	Sit() *Waiter[SitResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/Hold
	Hold() *Waiter[HoldResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/Kill
	Kill() *Waiter[KillResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/ReturnToHome
	ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *Waiter[ReturnToHomeResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetGlobalPositionTarget
	SetGlobalPositionTarget(
		latitude, longitude float64, altitude, heading float32,
		options ...opt.Option[opt.SetGlobalPositionTargetOption],
	) *Waiter[SetGlobalPositionTargetResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetRelativePositionTarget
	SetRelativePositionTarget(
		x, y, z, angle float32,
		options ...opt.Option[opt.SetRelativePositionTargetOption],
	) *Waiter[SetRelativePositionTargetResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetVelocityTarget
	SetVelocityTarget(
		xVel, yVel, zVel, angularVel float32,
		options ...opt.Option[opt.SetVelocityTargetOption],
	) *Waiter[SetVelocityTargetResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetGimbalAngleTarget
	SetGimbalAngleTarget(
		pitch, roll, yaw float32,
		options ...opt.Option[opt.SetGimbalAngleTargetOption],
	) *Waiter[SetGimbalAngleTargetResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetGimbalVelocityTarget
	SetGimbalVelocityTarget(
		pitchVel, rollVel, yawVel float32,
	) *Waiter[SetGimbalVelocityTargetResponse]
	// #exclude-ifndef steeleagle_protocol/v1/services/driver/StreamService/StreamTelemetry
	GetTelemetry(options ...opt.Option[opt.QueryOption]) *Waiter[[]Telemetry]
	GetDetectionResult(engine params.DetectionEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]DetectionResult]
	GetClassificationResult(engine params.ClassificationEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]ClassificationResult]
	GetGuidanceResult(engine params.GuidanceEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]GuidanceResult]
	GetPositionResult(engine params.PositionEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]PositionResult]
	GetGenericResult(engine params.GenericEngine, options ...opt.Option[opt.QueryOption]) *Waiter[[]GenericResult]
}
