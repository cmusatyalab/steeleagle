//package sdk
//
//import (
//	"context"
//	"fmt"
//
//	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
//	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
//	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
//	"github.com/cmusatyalab/steeleagle/sdk/types"
//	"google.golang.org/protobuf/proto"
//)
//
//type Device struct {
//	// TODO: Add cap file here once it is added to util
//	ctx     context.Context
//	control driverpb.ControlServiceClient
//	data    vehiclepb.DataServiceClient
//}
//
//func (d *Device) TakeOff(take_off_altitude float32) *waiter {
//	req := &driverpb.TakeOffRequest{TakeOffAltitude: take_off_altitude}
//	_, err := d.control.TakeOff(d.ctx, req)
//	return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusHolding), err)
//}
//
//func (d *Device) Land() *waiter {
//	req := &driverpb.LandRequest{}
//	_, err := d.control.Land(d.ctx, req)
//	return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusStopped), err)
//}
//
//func (d *Device) Hold() *waiter {
//	req := &driverpb.HoldRequest{}
//	_, err := d.control.Hold(d.ctx, req)
//	return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusHolding)
//}
//
//func (d *Device) Kill() *waiter {
//	req := &driverpb.KillRequest{}
//	_, err := d.control.Kill(d.ctx, req)
//	return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusStopped)
//}
//
//func (d *Device) SetHome(new_home types.GlobalPosition) *waiter {
//	req := &driverpb.SetHomeRequest{new_home: new_home.AsProto()}
//	_, err := d.control.SetHome(d.ctx, req)
//	return newWaiter(d.ctx, setHomePoller, err)
//}
//
//func (d *Device) ReturnToHome(
//    end_behavior types.ReturnToHomeEndBehavior,
//    min_return_altitude uint32,
//    final_altitude uint32) *waiter {
//    req := &driverpb.ReturnToHomeRequest{
//        end_behavior: end_behavior,
//        min_return_altitude: min_return_altitude,
//        final_altitude: final_altitude,
//    }
//    _, err := d.control.ReturnToHome(d.ctx, req)
//    if end_behavior == types.ReturnToHomeEndBehaviorHover {
//        return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusHolding), err)
//    } else {
//        return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusStopped), err)
//    }
//}
//
//func (d *Device) GoToGlobalPosition(
//    position types.GlobalPosition,
//    heading_mode types.HeadingMode,
//    altitude_mode types.AltitudeMode,
//    speed float32,
//    angular_speed float32) {
//    req := &driverpb.GoToGlobalPositionRequest{
//        position: commonpb.GlobalPosition{
//            latitude: position.latitude,
//            longitude: position.longitude,
//            altitude: position.altitude,
//            heading: position.heading,
//        },
//        heading_mode: heading_mode,
//        altitude_mode: altitude_mode,
//        speed: speed,
//        angular_speed: angular_speed,
//    }
//    _, err := d.control.GoToGlobalPosition(d.ctx, req)
//    return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusHolding), err)
//}
//
//func (d *Device) GoToRelativePosition(
//    position types.RelativePosition,
//    speed float32,
//    angular_speed float32,
//    frame types.ReferenceFrame) {
//    req := &driverpb.GoToRelativePositionRequest{
//        position: commonpb.RelativePosition{
//            x: position.x,
//            y: position.y,
//            z: position.z,
//            angle: position.angle,
//        },
//        speed: speed,
//        angular_speed: angular_speed,
//        frame: frame,
//    }
//    _, err := d.control.GoToRelativePosition(d.ctx, req)
//    return newWaiter(d.ctx, basePoller(req, d.data, types.MotionStatusHolding), err)
//}
//
//func (d *Device) SetVelocity(velocity types.Velocity, frame types.ReferenceFrame) {
//    req := &driverpb.SetVelocityRequest{
//        velocity: commonpb.Velocity{
//            x_vel: velocity.x_vel,
//            y_vel: velocity.y_vel,
//            z_vel: velocity.z_vel,
//            angular_vel: velocity.angular_vel,
//        },
//        frame: frame,
//    }
//    _, err := d.control.SetVelocity(d.ctx, req)
//    return newWaiter(d.ctx, velocityPoller(req, d.data), err)
//}
//
//
