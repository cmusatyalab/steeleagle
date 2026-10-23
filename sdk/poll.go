package sdk

import (
	"math"
	"time"

	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/rs/zerolog"
	"google.golang.org/protobuf/proto"
	anypb "google.golang.org/protobuf/types/known/anypb"
)

// pollFunc checks the status of a command until it is finished
// or it exits with error.
type pollFunc func(WaitOptions) error

// noPoll is the pollFunc of a command that is complete as soon as its RPC
// returns.
func noPoll(WaitOptions) error { return nil }

// pollTicker returns a ticker paced at d, or 100ms if d is
// non-positive.
func pollTicker(d time.Duration) *time.Ticker {
	if d <= 0 {
		d = 100 * time.Millisecond
	}
	return time.NewTicker(d)
}

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
// style RPC, logging to log. Expectations are end states, so a vehicle in the
// expected mode that is in transit is making progress; it has only stalled
// if it is at rest in the opposite way to the one expected, or reports no
// motion status (see stalledStatus).
func actionPoller[Resp isAction](log zerolog.Logger, v *vehicleContext, resp Resp) pollFunc {
	return func(w WaitOptions) error {
		ticker := pollTicker(w.Interval)
		defer ticker.Stop()
		timeoutC := timeoutChan(w.Timeout)
		mismatch := time.NewTimer(w.Stall)
		activeMismatch := false
		mismatch.Stop() // we only want to run this timer when a mismatch is detected
		defer mismatch.Stop()
		stall := time.NewTimer(w.Stall)
		activeStall := false
		stall.Stop() // we only want to run this timer when a stall is detected
		defer stall.Stop()
		log.Debug().
			Stringer("expected_mode", resp.GetExpectedMode()).
			Stringer("expected_status", resp.GetExpectedStatus()).
			Msg("polling for action expectation")
		var t *telemetrypb.Telemetry
		for {
			latest, err := fetchTelemetry(log, v)
			if err == nil { // only do check if we have telemetry
				t = latest
				if resp.GetExpectedMode() == t.GetMode() && resp.GetExpectedStatus() == t.GetMotionStatus() {
					log.Debug().Msg("action reached its expected mode and status")
					return nil
				} else if resp.GetExpectedMode() != t.GetMode() {
					if !activeMismatch { // wait to see if it is a transient mismatch
						log.Debug().
							Stringer("expected_mode", resp.GetExpectedMode()).
							Stringer("mode", t.GetMode()).
							Msg("mode mismatch, waiting to see if it persists")
						mismatch.Stop()
						mismatch.Reset(w.Stall)
						activeMismatch = true
					}
				} else {
					if activeMismatch { // mode matches again, so the mismatch resolved itself
						log.Debug().Msg("mode mismatch resolved")
						mismatch.Stop()
						activeMismatch = false
					}
					if !stalledStatus(resp.GetExpectedStatus(), t.GetMotionStatus()) {
						if activeStall { // making progress again, so the stall resolved itself
							log.Debug().Stringer("status", t.GetMotionStatus()).Msg("stall resolved")
							stall.Stop()
							activeStall = false
						}
					} else if !activeStall { // at rest the wrong way, or no status to go on
						log.Debug().
							Stringer("expected_status", resp.GetExpectedStatus()).
							Stringer("status", t.GetMotionStatus()).
							Msg("not making progress towards the expected status, waiting to see if it persists")
						stall.Stop()
						stall.Reset(w.Stall)
						activeStall = true
					}
				}
			}
			select {
			case <-timeoutC: // check for a timeout event
				log.Debug().
					Stringer("mode", t.GetMode()).
					Stringer("status", t.GetMotionStatus()).
					Msg("timed out waiting for action")
				return ErrTimeout
			case <-mismatch.C: // check for a persistent mode mismatch
				log.Debug().Stringer("mode", t.GetMode()).Msg("mode mismatch persisted, action was cancelled")
				return ErrCancelled
			case <-stall.C: // check for a stall event
				log.Debug().Stringer("status", t.GetMotionStatus()).Msg("stalled before reaching the expected status")
				return ErrFailedExpectation
			case <-v.ctx.Done():
				log.Debug().Err(v.ctx.Err()).Msg("vehicle context done while waiting for action")
				return ErrContextExpired
			case <-ticker.C: // pace polling to w.Interval
			}
		}
	}
}

// stalledStatus reports whether a vehicle with motion status got, while
// expecting status want, is not making progress towards it: at rest in the
// opposite way (holding when it should have stopped, or stopped when it
// should be holding), or reporting no motion status at all. In transit is
// never a stall.
func stalledStatus(want, got telemetrypb.MotionStatus) bool {
	const (
		holding     = telemetrypb.MotionStatus_MOTION_STATUS_HOLDING
		stopped     = telemetrypb.MotionStatus_MOTION_STATUS_STOPPED
		unspecified = telemetrypb.MotionStatus_MOTION_STATUS_UNSPECIFIED
	)
	return got == unspecified || (want == holding && got == stopped) || (want == stopped && got == holding)
}

// isGuidance makes sure that the response represents an guidance style RPC.
type isGuidance[S proto.Message] interface {
	GetSetpoint() S
	GetExpectedStatus() telemetrypb.MotionStatus
}

// guidancePoller is a poller function that checks the expectation of a
// guidance style RPC, logging to log.
func guidancePoller[S proto.Message, Resp isGuidance[S]](log zerolog.Logger, v *vehicleContext, resp Resp) pollFunc {
	return func(w WaitOptions) error {
		ticker := pollTicker(w.Interval)
		defer ticker.Stop()
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
		haveMinDistance := false
		log.Debug().
			Str("setpoint", string(proto.MessageName(resp.GetSetpoint()))).
			Msg("polling for setpoint")
		for {
			t, err := fetchTelemetry(log, v)
			// Only do check if we have telemetry and position info
			if err == nil && t.HasPositionInfo() {
				// Check the setpoints to make sure they match
				matches, matchErr := anyMatches(t.GetPositionInfo().GetSetpoint(), resp.GetSetpoint())
				if matchErr == nil && matches {
					if activeMismatch { // setpoint matches again, so the mismatch resolved itself
						log.Debug().Msg("setpoint mismatch resolved")
						mismatch.Stop()
						activeMismatch = false
					}
					distance, tolCheck, err := getDistance(log, resp.GetSetpoint(), t, w.Tolerances)
					if err != nil {
						// A failed measurement is never progress, so one that
						// persists trips the stall timer
						distance = float32(math.Inf(1))
					}
					// If we are within tolerance and have the right motion status, we have arrived
					if tolCheck && t.GetMotionStatus() == resp.GetExpectedStatus() {
						log.Debug().Float32("distance", distance).Msg("arrived at setpoint")
						return nil
					} else if !haveMinDistance { // first sample: nothing to compare progress against yet
						minDistance = distance
						haveMinDistance = true
						if err != nil {
							if !activeStall { // only reset the timer if there is an active stall
								log.Debug().Err(err).Msg("cannot measure distance to setpoint, waiting to see if it persists")
								stall.Stop()
								stall.Reset(w.Stall)
								activeStall = true
							}
						}
					} else if distance < minDistance { // a new best distance
						log.Trace().Float32("distance", distance).Msg("new best distance to setpoint")
						if activeStall {
							log.Debug().Float32("distance", distance).Msg("progress resumed")
						}
						minDistance = distance
						stall.Stop()
						activeStall = false
					} else if !activeStall { // no improvement over the best distance seen so far
						log.Debug().
							Err(err).
							Float32("distance", distance).
							Float32("best_distance", minDistance).
							Msg("no progress towards setpoint, waiting to see if it persists")
						stall.Stop()
						stall.Reset(w.Stall)
						activeStall = true
					}
				} else {
					if !activeMismatch { // wait to see if it is a transient mismatch
						log.Debug().Err(matchErr).Msg("setpoint mismatch, waiting to see if it persists")
						mismatch.Stop()
						mismatch.Reset(w.Stall)
						activeMismatch = true
					}
				}
			}
			select {
			case <-timeoutC: // check for a timeout event
				log.Debug().Float32("best_distance", minDistance).Msg("timed out waiting for setpoint")
				return ErrTimeout
			case <-stall.C: // check for a stall event
				log.Debug().Float32("best_distance", minDistance).Msg("stalled before reaching setpoint")
				return ErrFailedExpectation
			case <-mismatch.C: // check for a persistent setpoint mismatch
				log.Debug().Msg("setpoint mismatch persisted, command was overridden")
				return ErrCancelled
			case <-v.ctx.Done():
				log.Debug().Err(v.ctx.Err()).Msg("vehicle context done while waiting for setpoint")
				return ErrContextExpired
			case <-ticker.C: // pace polling to w.Interval
			}
		}
	}
}

// isGimbal makes sure that the response represents an guidance style RPC.
type isGimbal[S proto.Message] interface {
	GetSetpoint() S
}

// gimbalPoller is a poller function that checks the expectation of a
// gimbal style RPC, logging to log.
func gimbalPoller[S proto.Message, Resp isGimbal[S]](log zerolog.Logger, v *vehicleContext, resp Resp) pollFunc {
	return func(w WaitOptions) error {
		ticker := pollTicker(w.Interval)
		defer ticker.Stop()
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
		haveMinDistance := false
		log.Debug().
			Str("setpoint", string(proto.MessageName(resp.GetSetpoint()))).
			Msg("polling for setpoint")
		for {
			t, err := fetchTelemetry(log, v)
			// Only do check if we have telemetry and gimbal info
			if err == nil && t.HasGimbalInfo() {
				// Check the setpoints to make sure they match
				matches, matchErr := anyMatches(t.GetGimbalInfo().GetGimbalSetpoint(), resp.GetSetpoint())
				if matchErr == nil && matches {
					if activeMismatch { // setpoint matches again, so the mismatch resolved itself
						log.Debug().Msg("setpoint mismatch resolved")
						mismatch.Stop()
						activeMismatch = false
					}
					distance, tolCheck, err := getDistance(log, resp.GetSetpoint(), t, w.Tolerances)
					if err != nil {
						// A failed measurement is never progress, so one that
						// persists trips the stall timer
						distance = float32(math.Inf(1))
					}
					// If we are within tolerance and have the right motion status, we have arrived
					if tolCheck {
						log.Debug().Float32("distance", distance).Msg("arrived at setpoint")
						return nil
					} else if !haveMinDistance { // first sample: nothing to compare progress against yet
						minDistance = distance
						haveMinDistance = true
						if err != nil {
							if !activeStall { // only reset the timer if there is an active stall
								log.Debug().Err(err).Msg("cannot measure distance to setpoint, waiting to see if it persists")
								stall.Stop()
								stall.Reset(w.Stall)
								activeStall = true
							}
						}
					} else if distance < minDistance { // a new best distance
						log.Trace().Float32("distance", distance).Msg("new best distance to setpoint")
						if activeStall {
							log.Debug().Float32("distance", distance).Msg("progress resumed")
						}
						minDistance = distance
						stall.Stop()
						activeStall = false
					} else if !activeStall { // no improvement over the best distance seen so far
						log.Debug().
							Err(err).
							Float32("distance", distance).
							Float32("best_distance", minDistance).
							Msg("no progress towards setpoint, waiting to see if it persists")
						stall.Stop()
						stall.Reset(w.Stall)
						activeStall = true
					}
				} else {
					if !activeMismatch { // wait to see if it is a transient mismatch
						log.Debug().Err(matchErr).Msg("setpoint mismatch, waiting to see if it persists")
						mismatch.Stop()
						mismatch.Reset(w.Stall)
						activeMismatch = true
					}
				}
			}
			select {
			case <-timeoutC: // check for a timeout event
				log.Debug().Float32("best_distance", minDistance).Msg("timed out waiting for setpoint")
				return ErrTimeout
			case <-stall.C: // check for a stall event
				log.Debug().Float32("best_distance", minDistance).Msg("stalled before reaching setpoint")
				return ErrFailedExpectation
			case <-mismatch.C: // check for a persistent setpoint mismatch
				log.Debug().Msg("setpoint mismatch persisted, command was overridden")
				return ErrCancelled
			case <-v.ctx.Done():
				log.Debug().Err(v.ctx.Err()).Msg("vehicle context done while waiting for setpoint")
				return ErrContextExpired
			case <-ticker.C: // pace polling to w.Interval
			}
		}
	}
}

// fetchTelemetry retrieves the latest telemetry snapshot for v, translating
// gRPC and missing-payload failures into ErrInternal, which are logged to
// log.
func fetchTelemetry(log zerolog.Logger, v *vehicleContext) (*telemetrypb.Telemetry, error) {
	resp, err := v.data.GetTelemetry(v.ctx, &vehiclepb.GetTelemetryRequest{})
	if err != nil {
		log.Debug().Err(err).Msg("failed to fetch telemetry")
		return nil, ErrInternal
	}
	// Without a time range, only the most recent telemetry is returned
	telemetry := resp.GetTelemetry()
	if len(telemetry) == 0 {
		log.Debug().Msg("no telemetry available")
		return nil, ErrInternal
	}
	return telemetry[len(telemetry)-1], nil
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
