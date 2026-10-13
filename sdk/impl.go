package sdk

import (
	"context"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// Ctx gets the current context attached to a vehicleContext.
func (v *vehicleContext) Ctx() context.Context {
	return v.ctx
}

// TakeOff implements Vehicle.TakeOff for a vehicleContext.
func (v *vehicleContext) TakeOff(options ...opt.Option[opt.TakeOffOption]) *Waiter[TakeOffResponse] {
	req := &driverpb.TakeOffRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.TakeOff(v.ctx, req)

	return newWaiter[TakeOffResponse](
		&takeOffResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// Land implements Vehicle.Land for a vehicleContext.
func (v *vehicleContext) Land() *Waiter[LandResponse] {
	req := &driverpb.LandRequest{}
	resp, err := v.control.Land(v.ctx, req)

	return newWaiter[LandResponse](
		&landResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// Hold implements Vehicle.Hold for a vehicleContext.
func (v *vehicleContext) Hold() *Waiter[HoldResponse] {
	req := &driverpb.HoldRequest{}
	resp, err := v.control.Hold(v.ctx, req)

	return newWaiter[HoldResponse](
		&holdResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// Kill implements Vehicle.Kill for a vehicleContext.
func (v *vehicleContext) Kill() *Waiter[KillResponse] {
	req := &driverpb.KillRequest{}
	resp, err := v.control.Kill(v.ctx, req)

	return newWaiter[KillResponse](
		&killResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// ReturnToHome implements Vehicle.ReturnToHome for a vehicleContext.
func (v *vehicleContext) ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *Waiter[ReturnToHomeResponse] {
	req := &driverpb.ReturnToHomeRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.ReturnToHome(v.ctx, req)

	return newWaiter[ReturnToHomeResponse](
		&returnToHomeResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// SetGlobalPositionTarget implements Vehicle.SetGlobalPositionTarget for a vehicleContext.
func (v *vehicleContext) SetGlobalPositionTarget(
	latitude float64, longitude float64, altitude, heading float32,
	options ...opt.Option[opt.SetGlobalPositionTargetOption]) *Waiter[SetGlobalPositionTargetResponse] {
	req := &driverpb.SetGlobalPositionTargetRequest{}
	for _, option := range options {
		option(req)
	}
	position := &commonpb.GlobalPosition{}
	position.SetLatitude(latitude)
	position.SetLongitude(longitude)
	position.SetAltitude(altitude)
	position.SetHeading(heading)
	req.SetPosition(position)
	resp, err := v.control.SetGlobalPositionTarget(v.ctx, req)

	return newWaiter[SetGlobalPositionTargetResponse](
		&setGlobalPositionTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		guidancePoller(v, resp),
	)
}

// SetRelativePositionTarget implements Vehicle.SetRelativePositionTarget for a vehicleContext.
func (v *vehicleContext) SetRelativePositionTarget(
	x, y, z, angle float32,
	options ...opt.Option[opt.SetRelativePositionTargetOption]) *Waiter[SetRelativePositionTargetResponse] {
	req := &driverpb.SetRelativePositionTargetRequest{}
	for _, option := range options {
		option(req)
	}
	position := &commonpb.RelativePosition{}
	position.SetX(x)
	position.SetY(y)
	position.SetZ(z)
	position.SetAngle(angle)
	req.SetPosition(position)
	resp, err := v.control.SetRelativePositionTarget(v.ctx, req)

	return newWaiter[SetRelativePositionTargetResponse](
		&setRelativePositionTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		guidancePoller(v, resp),
	)
}

// SetVelocityTarget implements Vehicle.SetVelocityTarget for a vehicleContext.
func (v *vehicleContext) SetVelocityTarget(
	xVel, yVel, zVel, angularVel float32,
	options ...opt.Option[opt.SetVelocityTargetOption]) *Waiter[SetVelocityTargetResponse] {
	req := &driverpb.SetVelocityTargetRequest{}
	for _, option := range options {
		option(req)
	}
	velocity := &commonpb.Velocity{}
	velocity.SetXVel(xVel)
	velocity.SetYVel(yVel)
	velocity.SetZVel(zVel)
	velocity.SetAngularVel(angularVel)
	req.SetVelocity(velocity)
	resp, err := v.control.SetVelocityTarget(v.ctx, req)

	return newWaiter[SetVelocityTargetResponse](
		&setVelocityTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		guidancePoller(v, resp),
	)
}

// SetGimbalAngleTarget implements Vehicle.SetGimbalAngleTarget for a vehicleContext.
func (v *vehicleContext) SetGimbalAngleTarget(
	pitch, roll, yaw float32,
	options ...opt.Option[opt.SetGimbalAngleTargetOption]) *Waiter[SetGimbalAngleTargetResponse] {
	req := &driverpb.SetGimbalAngleTargetRequest{}
	for _, option := range options {
		option(req)
	}
	pose := &commonpb.Pose{}
	pose.SetPitch(pitch)
	pose.SetRoll(roll)
	pose.SetYaw(yaw)
	req.SetPose(pose)
	resp, err := v.control.SetGimbalAngleTarget(v.ctx, req)

	return newWaiter[SetGimbalAngleTargetResponse](
		&setGimbalAngleTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		gimbalPoller(v, resp),
	)
}

// SetGimbalVelocityTarget implements Vehicle.SetGimbalVelocityTarget for a vehicleContext.
func (v *vehicleContext) SetGimbalVelocityTarget(
	pitchVel, rollVel, yawVel float32) *Waiter[SetGimbalVelocityTargetResponse] {
	req := &driverpb.SetGimbalVelocityTargetRequest{}
	pose_vel := &commonpb.PoseVelocity{}
	pose_vel.SetPitchVel(pitchVel)
	pose_vel.SetRollVel(rollVel)
	pose_vel.SetYawVel(yawVel)
	req.SetPoseVelocity(pose_vel)
	resp, err := v.control.SetGimbalVelocityTarget(v.ctx, req)

	return newWaiter[SetGimbalVelocityTargetResponse](
		&setGimbalVelocityTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		gimbalPoller(v, resp),
	)
}

// GetTelemetry implements Vehicle.GetTelemetry for a vehicleContext.
func (v *vehicleContext) GetTelemetry() *Waiter[Telemetry] {
	req := &vehiclepb.GetTelemetryRequest{}
	resp, err := v.data.GetTelemetry(v.ctx, req)
	wrapper := &telemetryWrapper{}
	if resp != nil {
		wrapper.inner = resp.GetTelemetry() // need to make sure resp is not nil
	}

	return newWaiter[Telemetry](
		wrapper,
		grpcToSentinel(err),
		func(WaitOptions) error { return nil },
	)
}

var _ Vehicle = &vehicleContext{}
