package sdk

import (
    "context"
    "math"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/types"
	"google.golang.org/protobuf/proto"
)

// setHomePoller is the poll function for the SetHome RPC.
func setHomePoller(req *driverpb.SetHomeRequest, data vehiclepb.DataServiceClient) pollFunc {
	return func(ctx context.Context) (bool, error) {
		t, err := d.data.GetTelemetry(vehiclepb.GetTelemetryRequest{})
		if err != nil {
			return false, err
		}
		if match, err := anyMatches(t.Telemetry.PositionInfo.Home, req.new_home); match {
			return true, nil
		}
        return false, nil
	}
}

// areClose is a helper function for checking if two floating point numbers
// are close within a tolerance epsilon.
func areClose(a, b, epsilon float32) bool {
    return math.Abs(a - b) <= epsilon
}

// setVelocityPoller is the poll function for the SetVelocity RPC.
func setVelocityPoller(req *driverpb.SetVelocityRequest, data vehiclepb.DataServiceClient, tol float32) pollFunc {
    return func(ctx context.Context) (bool, error) {
		t, err := data.GetTelemetry(vehiclepb.GetTelemetryRequest{})
		if err != nil {
			return false, err
		}
        if match, err := anyMatches(t.Telemetry.PositionInfo.Setpoint, req); !match {
           return false, fmt.Errorf("vehicle has changed its setpoint") 
        }
        var velocity commonpb.Velocity
        if req.frame <= 1 { // body reference frame
            velocity = t.Telemetry.PositionInfo.VelocityBody
        } else { // NEU reference frame
            velocity = t.Telemetry.PositionInfo.VelocityNeu
        }
        if areClose(velocity.X, req.velocity.X, tol) &&
            areClose(velocity.Y, req.velocity.Y, tol) &&
            areClose(velocity.Z, req.velocity.Z, tol) {
            return true, nil
        }
        return false, nil
    }
}

// basePoller is the basic poll function used by most device methods.
func basePoller(req proto.Message, data vehiclepb.DataServiceClient, endState types.MotionStatus) pollFunc {
	return func(ctx context.Context) (bool, error) {
		t, err := data.GetTelemetry(ctx, &vehiclepb.GetTelemetryRequest{})
		if err != nil {
			return false, err
		}
		if match, err := anyMatches(t.Telemetry.PositionInfo.Setpoint, req); match {
			if err != nil {
				return false, err
			} else if t.Telemetry.PositionInfo.MotionStatus == endState || endState == types.MotionStatusUnspecified {
				return true, nil
			} else {
				return false, nil
			}
		} else {
			return true, fmt.Errorf("vehicle has changed its setpoint")
		}
	}
}
