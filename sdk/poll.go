//go:build ignore

package sdk

import (
	"time"

	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/golang/protobuf/proto"
	anypb "google.golang.org/protobuf/types/known/anypb"
)

// pollFunc checks the status of a command until it is finished
// or it exits with error.
type pollFunc func(opt.WaitOptions) error

// actionPoller is a poller function that checks the expectation of an action
// style RPC.
func actionPoller(v *vehicleContext, resp proto.Message) pollFunc {
	return func(w opt.WaitOptions) error {
		timeout := time.NewTimer(w.Timeout)
		defer timeout.Stop()
		for {
			t, err := fetchTelemetry(v)
			if err == nil { // only do check if we have telemetry
				if resp.GetExpectedMode() == t.GetMode() && resp.GetExpectedStatus() == t.GetMotionStatus() {
					return nil
				} else if resp.GetExpectedMode() != t.GetMode() {
					return ErrCancelled
				}
			}
			select {
			case <-timeout.C: // check for a timeout event
				return ErrTimeout
			case <-v.ctx.Done():
				return ErrContextExpired
			default:
			}
		}
	}
}

// guidancePoller is a poller function that checks the expectation of a
// guidance style RPC.
func guidancePoller(v *vehicleContext, resp proto.Message) pollFunc {
	return func(w opt.WaitOptions) error {
		timeout := time.NewTimer(w.Timeout)
		defer timeout.Stop()
		stall := time.NewTimer(w.Stall)
		activeStall := false
		stall.Stop() // we only want to run this timer when a stall is detected
		defer stall.Stop()
		lastDistance := 0.0
		for {
			t, err := fetchTelemetry(v)
			// Only do check if we have telemetry and position info
			if err == nil && t.HasPositionInfo() {
				// Check the setpoints to make sure they match
				if anyMatches(t.GetPositionInfo().GetSetpoint(), resp.GetSetpoint()) {
					distance, tolCheck, err = getDistance(resp.GetSetpoint(), t, w.Tolerances)
					// If we are within tolerance and have the right motion status, we have arrived
					if tolCheck && t.GetMotionStatus() == resp.GetExpectedStatus() {
						return nil
					} else if lastDistance { // we have already set lastDistance so we do a stall check
						if distance >= lastDistance { // stall is active
							if !activeStall { // only reset the timer if there is an active stall
								stall.Stop()
								stall.Reset(w.Stall)
								activeStall = true
							}
						} else { // stall can be reset
							stall.Stop()
						}
					} else if err != nil {
						if !activeStall { // only reset the timer if there is an active stall
							stall.Stop()
							stall.Reset(w.Stall)
							activeStall = true
						}
					}
					lastDistance = distance
				} else {
					return ErrCancelled
				}
			}
			select {
			case <-timeout.C: // check for a timeout event
				return ErrTimeout
			case <-stall.C: // check for a stall event
				return ErrFailedExpectation
			case <-v.ctx.Done():
				return ErrContextExpired
			default:
			}
		}
	}
}

// gimbalPoller is a poller function that checks the expectation of a
// gimbal style RPC.
func gimbalPoller(v *vehicleContext, resp proto.Message) pollFunc {
	return func(w opt.WaitOptions) error {
		timeout := time.NewTimer(w.Timeout)
		defer timeout.Stop()
		stall := time.NewTimer(w.Stall)
		activeStall := false
		stall.Stop() // we only want to run this timer when a stall is detected
		defer stall.Stop()
		lastDistance := 0.0
		for {
			t, err := fetchTelemetry(v)
			// Only do check if we have telemetry and gimbal info
			if err == nil && t.HasGimbalInfo() {
				// Check the setpoints to make sure they match
				if anyMatches(t.GetGimbalInfo().GetGimbalSetpoint(), resp.GetSetpoint()) {
					distance, tolCheck, err = getDistance(resp.GetSetpoint(), t, w.Tolerances)
					// If we are within tolerance and have the right motion status, we have arrived
					if tolCheck {
						return nil
					} else if lastDistance { // we have already set lastDistance so we do a stall check
						if distance >= lastDistance { // stall is active
							if !activeStall { // only reset the timer if there is an active stall
								stall.Stop()
								stall.Reset(w.Stall)
								activeStall = true
							}
						} else { // stall can be reset
							stall.Stop()
						}
					} else if err != nil {
						if !activeStall { // only reset the timer if there is an active stall
							stall.Stop()
							stall.Reset(w.Stall)
							activeStall = true
						}
					}
					lastDistance = distance
				} else {
					return ErrCancelled
				}
			}
			select {
			case <-timeout.C: // check for a timeout event
				return ErrTimeout
			case <-stall.C: // check for a stall event
				return ErrFailedExpectation
			case <-v.ctx.Done():
				return ErrContextExpired
			default:
			}
		}
	}
}

// fetchTelemetry retrieves the latest telemetry snapshot for v, translating
// gRPC and missing-payload failures into ErrInternal.
func fetchTelemetry(v *vehicleContext) (*telemetrypb.Telemetry, error) {
	resp, err := v.data.GetTelemetry(v.ctx, &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		return nil, ErrInternal
	}
	if !resp.HasTelemetry() {
		return nil, ErrInternal
	}
	return resp.GetTelemetry(), nil
}

// anyMatches reports whether a holds a message of the same type as want,
// and if so, whether its content is equal to want.
func anyMatches(a *anypb.Any, want proto.Message) (bool, error) {
	// Compares a.TypeUrl's message name against want's
	// descriptor, without unmarshalling the payload
	if !a.MessageIs(want) {
		return false, nil
	}

	// Unmarshal into a fresh instance of the same concrete type as want
	got := want.ProtoReflect().New().Interface()
	if err := a.UnmarshalTo(got); err != nil {
		return false, err
	}

	return proto.Equal(got, want), nil
}
