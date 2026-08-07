//go:build ignore

package sdk

import (
	"context"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

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
		basePoller(v, req, enums.PositionInfo_MotionStatusHolding),
	)
}

func (v *vehicleContext) Land() *waiter[LandResponse] {
	req := &driverpb.LandRequest{}
	resp, err := v.control.Land(v.ctx, req)

	return newWaiter[LandResponse](
		v.ctx,
		&landResponseWrapper{inner: resp},
		grpcToSentinel(err),
		basePoller(v, req, enums.PositionInfo_MotionStatusStopped),
	)
}

func (v *vehicleContext) Hold() *waiter[HoldResponse] {
	req := &driverpb.HoldRequest{}
	resp, err := v.control.Hold(v.ctx, req)

	return newWaiter[HoldResponse](
		v.ctx,
		&holdResponseWrapper{inner: resp},
		grpcToSentinel(err),
		basePoller(v, req, enums.PositionInfo_MotionStatusHolding),
	)
}

func (v *vehicleContext) Kill() *waiter[KillResponse] {
	req := &driverpb.KillRequest{}
	resp, err := v.control.Kill(v.ctx, req)

	return newWaiter[KillResponse](
		v.ctx,
		&killResponseWrapper{inner: resp},
		grpcToSentinel(err),
		basePoller(v, req, enums.PositionInfo_MotionStatusStopped),
	)
}

func (v *vehicleContext) SetHome(latitude float64, longitude float64, altitude float32) *waiter[SetHomeResponse] {
	req := &driverpb.SetHomeRequest{}
	req.GetNewHome().SetLatitude(latitude)
	req.GetNewHome().SetLongitude(longitude)
	req.GetNewHome().SetAltitude(altitude)
	resp, err := v.control.SetHome(v.ctx, req)

	return newWaiter[SetHomeResponse](
		v.ctx,
		&setHomeResponseWrapper{inner: resp},
		grpcToSentinel(err),
		setHomePoller(v, req),
	)
}

func (v *vehicleContext) ReturnToHome(options ...opt.Option[opt.ReturnToHomeOption]) *waiter[ReturnToHomeResponse] {
	req := &driverpb.ReturnToHomeRequest{}
	for _, option := range options {
		option(req)
	}
	resp, err := v.control.ReturnToHome(v.ctx, req)

	if req.GetEndBehavior() <= 1 { // hover end behavior
		return newWaiter[ReturnToHomeResponse](
			v.ctx,
			&returnToHomeResponseWrapper{inner: resp},
			grpcToSentinel(err),
			basePoller(v, req, enums.PositionInfo_MotionStatusHolding),
		)
	} else { // land end behavior
		return newWaiter[ReturnToHomeResponse](
			v.ctx,
			&returnToHomeResponseWrapper{inner: resp},
			grpcToSentinel(err),
			basePoller(v, req, enums.PositionInfo_MotionStatusStopped),
		)
	}
}

func (v *vehicleContext) GoToGlobalPosition(
	latitude float64, longitude float64, altitude, heading float32,
	options ...opt.Option[opt.GoToGlobalPositionOption]) *waiter[GoToGlobalPositionResponse] {
	req := &driverpb.GoToGlobalPositionRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPosition().SetLatitude(latitude)
	req.GetPosition().SetLongitude(longitude)
	req.GetPosition().SetAltitude(altitude)
	req.GetPosition().SetHeading(heading)
	resp, err := v.control.GoToGlobalPosition(v.ctx, req)

	return newWaiter[GoToGlobalPositionResponse](
		v.ctx,
		&goToGlobalPositionResponseWrapper{inner: resp},
		grpcToSentinel(err),
		basePoller(v, req, enums.PositionInfo_MotionStatusHolding),
	)
}

func (v *vehicleContext) GoToRelativePosition(
	x, y, z, angle float32,
	options ...opt.Option[opt.GoToRelativePositionOption]) *waiter[GoToRelativePositionResponse] {
	req := &driverpb.GoToRelativePositionRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPosition().SetX(x)
	req.GetPosition().SetY(y)
	req.GetPosition().SetZ(z)
	req.GetPosition().SetAngle(angle)
	resp, err := v.control.GoToRelativePosition(v.ctx, req)

	return newWaiter[GoToRelativePositionResponse](
		v.ctx,
		&goToRelativePositionResponseWrapper{inner: resp},
		grpcToSentinel(err),
		basePoller(v, req, enums.PositionInfo_MotionStatusHolding),
	)
}

func (v *vehicleContext) SetVelocity(
	xVel, yVel, zVel, angularVel float32,
	options ...opt.Option[opt.SetVelocityOption]) *waiter[SetVelocityResponse] {
	req := &driverpb.SetVelocityRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetVelocity().SetXVel(xVel)
	req.GetVelocity().SetYVel(yVel)
	req.GetVelocity().SetZVel(zVel)
	req.GetVelocity().SetAngularVel(angularVel)
	resp, err := v.control.SetVelocity(v.ctx, req)

	return newWaiter[SetVelocityResponse](
		v.ctx,
		&setVelocityResponseWrapper{inner: resp},
		grpcToSentinel(err),
		basePoller(v, req, enums.PositionInfo_MotionStatusInTransit),
	)
}

func (v *vehicleContext) SetGimbalPose(
	pitch, roll, yaw float32,
	options ...opt.Option[opt.SetGimbalPoseOption]) *waiter[SetGimbalPoseResponse] {
	req := &driverpb.SetGimbalPoseRequest{}
	for _, option := range options {
		option(req)
	}
	req.GetPose().SetPitch(pitch)
	req.GetPose().SetRoll(roll)
	req.GetPose().SetYaw(yaw)
	resp, err := v.control.SetGimbalPose(v.ctx, req)

	return newWaiter[SetGimbalPoseResponse](
		v.ctx,
		&setGimbalPoseResponseWrapper{inner: resp},
		grpcToSentinel(err),
		setGimbalPosePoller(v, req),
	)
}

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
		func(context.Context) (bool, error) { return true, nil },
	)
}
