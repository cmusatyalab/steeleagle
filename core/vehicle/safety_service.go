package vehicle

import (
	"context"
	"time"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/protobuf/types/known/durationpb"
)

// GetFailsafeState returns the current failsafe state of the vehicle, along
// with the downtime of its control and data planes.
func (v *Vehicle) GetFailsafeState(
	ctx context.Context,
	req *vehiclepb.GetFailsafeStateRequest,
) (*vehiclepb.GetFailsafeStateResponse, error) {
	v.safetyMu.Lock()
	defer v.safetyMu.Unlock()
	return vehiclepb.GetFailsafeStateResponse_builder{
		State: v.failsafe,
		Time:  durationpb.New(time.Since(v.failsafeTime)),
	}.Build(), nil
}

// SetControlFailsafeBehavior sets what the vehicle does after entering a
// control failsafe, when the daemon loses contact with its orchestrator.
func (v *Vehicle) SetControlFailsafeBehavior(
	ctx context.Context,
	req *vehiclepb.SetControlFailsafeBehaviorRequest,
) (*vehiclepb.SetControlFailsafeBehaviorResponse, error) {
	behavior := behaviorOrHold(req.GetBehavior())
	v.safetyMu.Lock()
	v.controlBehavior = behavior
	v.safetyMu.Unlock()
	v.log.Info().Stringer("behavior", behavior).Msg("control failsafe behavior set")
	return &vehiclepb.SetControlFailsafeBehaviorResponse{}, nil
}

// SetDataFailsafeBehavior sets what the vehicle does after entering a data
// failsafe, when the vehicle loses contact with its RCS.
func (v *Vehicle) SetDataFailsafeBehavior(
	ctx context.Context,
	req *vehiclepb.SetDataFailsafeBehaviorRequest,
) (*vehiclepb.SetDataFailsafeBehaviorResponse, error) {
	behavior := behaviorOrHold(req.GetBehavior())
	v.safetyMu.Lock()
	v.dataBehavior = behavior
	v.safetyMu.Unlock()
	v.log.Info().Stringer("behavior", behavior).Msg("data failsafe behavior set")
	return &vehiclepb.SetDataFailsafeBehaviorResponse{}, nil
}

// behaviorOrHold returns behavior, or hold if it is unspecified.
func behaviorOrHold(behavior vehiclepb.FailsafeBehavior) vehiclepb.FailsafeBehavior {
	if behavior == vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_UNSPECIFIED {
		return vehiclepb.FailsafeBehavior_FAILSAFE_BEHAVIOR_HOLD
	}
	return behavior
}
