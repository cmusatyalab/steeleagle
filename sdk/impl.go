package sdk

import (
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// TakeOff implements Vehicle.TakeOff for a vehicleContext.
func (v *vehicleContext) TakeOff(options ...opt.Option[opt.TakeOffOption]) *waiter[TakeOffResponse] {
	req := &driverpb.TakeOffRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.TakeOff(v.ctx, req)

	return newWaiter[TakeOffResponse](
		v.ctx,
		&takeOffResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// Land implements Vehicle.Land for a vehicleContext.
func (v *vehicleContext) Land() *waiter[LandResponse] {
	req := &driverpb.LandRequest{}
	resp, err := v.control.Land(v.ctx, req)

	return newWaiter[LandResponse](
		v.ctx,
		&landResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// Hold implements Vehicle.Hold for a vehicleContext.
func (v *vehicleContext) Hold() *waiter[HoldResponse] {
	req := &driverpb.HoldRequest{}
	resp, err := v.control.Hold(v.ctx, req)

	return newWaiter[HoldResponse](
		v.ctx,
		&holdResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// Kill implements Vehicle.Kill for a vehicleContext.
func (v *vehicleContext) Kill() *waiter[KillResponse] {
	req := &driverpb.KillRequest{}
	resp, err := v.control.Kill(v.ctx, req)

	return newWaiter[KillResponse](
		v.ctx,
		&killResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// ReturnToHome implements Vehicle.ReturnToHome for a vehicleContext.
func (v *vehicleContext) ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *waiter[ReturnToHomeResponse] {
	req := &driverpb.ReturnToHomeRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.ReturnToHome(v.ctx, req)

	return newWaiter[ReturnToHomeResponse](
		v.ctx,
		&returnToHomeResponseWrapper{inner: resp},
		grpcToSentinel(err),
		actionPoller(v, resp),
	)
}

// SetGlobalPositionTarget implements Vehicle.SetGlobalPositionTarget for a vehicleContext.
func (v *vehicleContext) SetGlobalPositionTarget(
	latitude float64, longitude float64, altitude, heading float32,
	options ...opt.Option[opt.SetGlobalPositionTargetOption]) *waiter[SetGlobalPositionTargetResponse] {
	req := &driverpb.SetGlobalPositionTargetRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPosition().SetLatitude(latitude)
	req.GetPosition().SetLongitude(longitude)
	req.GetPosition().SetAltitude(altitude)
	req.GetPosition().SetHeading(heading)
	resp, err := v.control.SetGlobalPositionTarget(v.ctx, req)

	return newWaiter[SetGlobalPositionTargetResponse](
		v.ctx,
		&setGlobalPositionTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		guidancePoller(v, resp),
	)
}

// SetRelativePositionTarget implements Vehicle.SetRelativePositionTarget for a vehicleContext.
func (v *vehicleContext) SetRelativePositionTarget(
	x, y, z, angle float32,
	options ...opt.Option[opt.SetRelativePositionTargetOption]) *waiter[SetRelativePositionTargetResponse] {
	req := &driverpb.SetRelativePositionTargetRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPosition().SetX(x)
	req.GetPosition().SetY(y)
	req.GetPosition().SetZ(z)
	req.GetPosition().SetAngle(angle)
	resp, err := v.control.SetRelativePositionTarget(v.ctx, req)

	return newWaiter[SetRelativePositionTargetResponse](
		v.ctx,
		&setRelativePositionTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		guidancePoller(v, resp),
	)
}

// SetVelocityTarget implements Vehicle.SetVelocityTarget for a vehicleContext.
func (v *vehicleContext) SetVelocityTarget(
	xVel, yVel, zVel, angularVel float32,
	options ...opt.Option[opt.SetVelocityTargetOption]) *waiter[SetVelocityTargetResponse] {
	req := &driverpb.SetVelocityTargetRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetVelocity().SetXVel(xVel)
	req.GetVelocity().SetYVel(yVel)
	req.GetVelocity().SetZVel(zVel)
	req.GetVelocity().SetAngularVel(angularVel)
	resp, err := v.control.SetVelocityTarget(v.ctx, req)

	return newWaiter[SetVelocityTargetResponse](
		v.ctx,
		&setVelocityTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		guidancePoller(v, resp),
	)
}

// SetGimbalAngleTarget implements Vehicle.SetGimbalAngleTarget for a vehicleContext.
func (v *vehicleContext) SetGimbalAngleTarget(
	pitch, roll, yaw float32,
	options ...opt.Option[opt.SetGimbalAngleTargetOption]) *waiter[SetGimbalAngleTargetResponse] {
	req := &driverpb.SetGimbalAngleTargetRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPose().SetPitch(pitch)
	req.GetPose().SetRoll(roll)
	req.GetPose().SetYaw(yaw)
	resp, err := v.control.SetGimbalAngleTarget(v.ctx, req)

	return newWaiter[SetGimbalAngleTargetResponse](
		v.ctx,
		&setGimbalAngleTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		gimbalPoller(v, resp),
	)
}

// SetGimbalVelocityTarget implements Vehicle.SetGimbalVelocityTarget for a vehicleContext.
func (v *vehicleContext) SetGimbalVelocityTarget(
	pitchVel, rollVel, yawVel float32,
	options ...opt.Option[opt.SetGimbalVelocityTargetOption]) *waiter[SetGimbalVelocityTargetResponse] {
	req := &driverpb.SetGimbalVelocityTargetRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPoseVelocity().SetPitchVel(pitchVel)
	req.GetPoseVelocity().SetRollVel(rollVel)
	req.GetPoseVelocity().SetYawVel(yawVel)
	resp, err := v.control.SetGimbalVelocityTarget(v.ctx, req)

	return newWaiter[SetGimbalVelocityTargetResponse](
		v.ctx,
		&setGimbalVelocityTargetResponseWrapper{inner: resp},
		grpcToSentinel(err),
		gimbalPoller(v, resp),
	)
}

// GetTelemetry implements Vehicle.GetTelemetry for a vehicleContext.
func (v *vehicleContext) GetTelemetry() *waiter[Telemetry] {
	req := &vehiclepb.GetTelemetryRequest{}
	resp, err := v.data.GetTelemetry(v.ctx, req)
	wrapper := &telemetryWrapper{}
	if resp != nil {
		wrapper.inner = resp.GetTelemetry() // need to make sure resp is not nil
	}

	return newWaiter[Telemetry](
		v.ctx,
		wrapper,
		grpcToSentinel(err),
		func(opt.WaitOptions) error { return nil },
	)
}
