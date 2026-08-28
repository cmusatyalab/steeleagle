package sdk

import (
	"time"

	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"google.golang.org/protobuf/proto"
	anypb "google.golang.org/protobuf/types/known/anypb"
)

// pollFunc checks the status of a command until it is finished
// or it exits with error.
type pollFunc func(opt.WaitOptions) error

// timeoutChan returns a channel that fires once after d, or, per
// WaitOptions.Timeout's documented zero-means-never-time-out contract, a nil
// channel that never fires when d <= 0.
func timeoutChan(d time.Duration) <-chan time.Time {
	if d <= 0 {
		return nil
	}
	return time.NewTimer(d).C
}

// isAction makes sure that the response represents an action style RPC.
type isAction interface {
	GetExpectedMode() telemetrypb.Mode
	GetExpectedStatus() telemetrypb.MotionStatus
}

// actionPoller is a poller function that checks the expectation of an action
// style RPC.
func actionPoller[Resp isAction](v *vehicleContext, resp Resp) pollFunc {
	return func(w opt.WaitOptions) error {
		timeoutC := timeoutChan(w.Timeout)
		mismatch := time.NewTimer(w.Stall)
		activeMismatch := false
		mismatch.Stop() // we only want to run this timer when a mismatch is detected
		defer mismatch.Stop()
		for {
			t, err := fetchTelemetry(v)
			if err == nil { // only do check if we have telemetry
				if resp.GetExpectedMode() == t.GetMode() && resp.GetExpectedStatus() == t.GetMotionStatus() {
					return nil
				} else if resp.GetExpectedMode() != t.GetMode() {
					if !activeMismatch { // wait to see if it is a transient mismatch
						mismatch.Stop()
						mismatch.Reset(w.Stall)
						activeMismatch = true
					}
				} else if activeMismatch { // mode matches again, so the mismatch resolved itself
					mismatch.Stop()
					activeMismatch = false
				}
			}
			select {
			case <-timeoutC: // check for a timeout event
				return ErrTimeout
			case <-mismatch.C: // check for a persistent mode mismatch
				return ErrCancelled
			case <-v.ctx.Done():
				return ErrContextExpired
			case <-time.After(w.Interval): // pace polling to w.Interval
			}
		}
	}
}

// isGuidance makes sure that the response represents an guidance style RPC.
type isGuidance[S proto.Message] interface {
	GetSetpoint() S
	GetExpectedStatus() telemetrypb.MotionStatus
}

// guidancePoller is a poller function that checks the expectation of a
// guidance style RPC.
func guidancePoller[S proto.Message, Resp isGuidance[S]](v *vehicleContext, resp Resp) pollFunc {
	return func(w opt.WaitOptions) error {
		timeoutC := timeoutChan(w.Timeout)
		stall := time.NewTimer(w.Stall)
		activeStall := false
		stall.Stop() // we only want to run this timer when a stall is detected
		defer stall.Stop()
		mismatch := time.NewTimer(w.Stall)
		activeMismatch := false
		mismatch.Stop() // we only want to run this timer when a mismatch is detected
		defer mismatch.Stop()
		var minDistance float32
		haveMinDistance := false // distinguishes "no sample yet" from a legitimate 0.0 minimum
		for {
			t, err := fetchTelemetry(v)
			// Only do check if we have telemetry and position info
			if err == nil && t.HasPositionInfo() {
				// Check the setpoints to make sure they match
				matches, matchErr := anyMatches(t.GetPositionInfo().GetSetpoint(), resp.GetSetpoint())
				if matchErr == nil && matches {
					if activeMismatch { // setpoint matches again, so the mismatch resolved itself
						mismatch.Stop()
						activeMismatch = false
					}
					distance, tolCheck, err := getDistance(resp.GetSetpoint(), t, w.Tolerances)
					// If we are within tolerance and have the right motion status, we have arrived
					if tolCheck && t.GetMotionStatus() == resp.GetExpectedStatus() {
						return nil
					} else if !haveMinDistance { // first sample: nothing to compare progress against yet
						minDistance = distance
						haveMinDistance = true
						if err != nil {
							if !activeStall { // only reset the timer if there is an active stall
								stall.Stop()
								stall.Reset(w.Stall)
								activeStall = true
							}
						}
					} else if distance < minDistance { // a new best distance: genuine progress
						minDistance = distance
						stall.Stop()
						activeStall = false
					} else if !activeStall { // no improvement over the best distance seen so far
						stall.Stop()
						stall.Reset(w.Stall)
						activeStall = true
					}
				} else {
					if !activeMismatch { // wait to see if it is a transient mismatch
						mismatch.Stop()
						mismatch.Reset(w.Stall)
						activeMismatch = true
					}
				}
			}
			select {
			case <-timeoutC: // check for a timeout event
				return ErrTimeout
			case <-stall.C: // check for a stall event
				return ErrFailedExpectation
			case <-mismatch.C: // check for a persistent setpoint mismatch
				return ErrCancelled
			case <-v.ctx.Done():
				return ErrContextExpired
			case <-time.After(w.Interval): // pace polling to w.Interval
			}
		}
	}
}

// isGimbal makes sure that the response represents an guidance style RPC.
type isGimbal[S proto.Message] interface {
	GetSetpoint() S
}

// gimbalPoller is a poller function that checks the expectation of a
// gimbal style RPC.
func gimbalPoller[S proto.Message, Resp isGimbal[S]](v *vehicleContext, resp Resp) pollFunc {
	return func(w opt.WaitOptions) error {
		timeoutC := timeoutChan(w.Timeout)
		stall := time.NewTimer(w.Stall)
		activeStall := false
		stall.Stop() // we only want to run this timer when a stall is detected
		defer stall.Stop()
		mismatch := time.NewTimer(w.Stall)
		activeMismatch := false
		mismatch.Stop() // we only want to run this timer when a mismatch is detected
		defer mismatch.Stop()
		var minDistance float32
		haveMinDistance := false // distinguishes "no sample yet" from a legitimate 0.0 minimum
		for {
			t, err := fetchTelemetry(v)
			// Only do check if we have telemetry and gimbal info
			if err == nil && t.HasGimbalInfo() {
				// Check the setpoints to make sure they match
				matches, matchErr := anyMatches(t.GetGimbalInfo().GetGimbalSetpoint(), resp.GetSetpoint())
				if matchErr == nil && matches {
					if activeMismatch { // setpoint matches again, so the mismatch resolved itself
						mismatch.Stop()
						activeMismatch = false
					}
					distance, tolCheck, err := getDistance(resp.GetSetpoint(), t, w.Tolerances)
					// If we are within tolerance and have the right motion status, we have arrived
					if tolCheck {
						return nil
					} else if !haveMinDistance { // first sample: nothing to compare progress against yet
						minDistance = distance
						haveMinDistance = true
						if err != nil {
							if !activeStall { // only reset the timer if there is an active stall
								stall.Stop()
								stall.Reset(w.Stall)
								activeStall = true
							}
						}
					} else if distance < minDistance { // a new best distance: genuine progress
						minDistance = distance
						stall.Stop()
						activeStall = false
					} else if !activeStall { // no improvement over the best distance seen so far
						stall.Stop()
						stall.Reset(w.Stall)
						activeStall = true
					}
				} else {
					if !activeMismatch { // wait to see if it is a transient mismatch
						mismatch.Stop()
						mismatch.Reset(w.Stall)
						activeMismatch = true
					}
				}
			}
			select {
			case <-timeoutC: // check for a timeout event
				return ErrTimeout
			case <-stall.C: // check for a stall event
				return ErrFailedExpectation
			case <-mismatch.C: // check for a persistent setpoint mismatch
				return ErrCancelled
			case <-v.ctx.Done():
				return ErrContextExpired
			case <-time.After(w.Interval): // pace polling to w.Interval
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
