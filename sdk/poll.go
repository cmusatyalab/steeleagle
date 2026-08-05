//go:build ignore

package sdk

import (
	"context"
	"fmt"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/types"
	"google.golang.org/protobuf/proto"
)

// basePoller is the basic poll function used by most device methods.
func basePoller(req proto.Message) pollFunc {
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
