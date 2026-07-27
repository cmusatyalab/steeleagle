package sdk

import (
	"context"
	"fmt"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/types"
	"google.golang.org/protobuf/proto"
)

type Device struct {
	// TODO: Add cap file here once it is added to util
	ctx     context.Context
	control driverpb.ControlServiceClient
	data    vehiclepb.DataServiceClient
}

func (d *Device) TakeOff(take_off_altitude float32) (*waiter, error) {
	req := &driverpb.TakeOffRequest{TakeOffAltitude: take_off_altitude}
	_, err := d.control.TakeOff(d.ctx, req)
	return newWaiter(ctx, basePoller(req, d.data, 1), err), err
}

func (d *Device) Land() (*waiter, error) {
	req := &driverpb.LandRequest{}
	_, err := d.control.Land(d.ctx, req)
	return newWaiter(ctx, basePoller(req, d.data, 3), err), err
}

func (d *Device) Hold() (*waiter, error) {
	req := &driverpb.HoldRequest{}
	_, err := d.control.Hold(d.ctx, req)
	return newWaiter(ctx, basePoller(req, d.data, 2), err), err
}

func (d *Device) Kill() (*waiter, error) {
	req := &driverpb.KillRequest{}
	_, err := d.control.Kill(d.ctx, req)
	return newWaiter(ctx, basePoller(req, d.data, 3), err), err
}

func (d *Device) SetHome(new_home types.GlobalPosition) (*waiter, error) {
	req := &driverpb.SetHomeRequest{new_home: new_home.AsProto()}
	_, err := d.control.SetHome(d.ctx, req)
	poller := func(ctx context.Context) (bool, error) {
		t, err := d.data.GetTelemetry(ctx, &vehiclepb.GetTelemetryRequest{})
		if err != nil {
			return false, err
		}
		if match, err := anyMatches(t.Telemetry.PositionInfo.Home, req.new_home); match {
			return true, nil
		}
	}
	return newWaiter(ctx, poller, err), err
}

// basePoller is the basic poll function used by most device methods.
func basePoller(req proto.Message, data vehiclepb.DataServiceClient, endState int) pollFunc {
	return func(ctx context.Context) (bool, error) {
		t, err := data.GetTelemetry(ctx, &vehiclepb.GetTelemetryRequest{})
		if err != nil {
			return false, err
		}
		if match, err := anyMatches(t.Telemetry.PositionInfo.Setpoint, req); match {
			if err != nil {
				return false, err
			} else if t.Telemetry.PositionInfo.MotionStatus == endState || !endState {
				return true, nil
			} else {
				return false, nil
			}
		} else {
			return true, fmt.Errorf("vehicle has changed its setpoint")
		}
	}
}
