package sdk

import (
	"context"
	"errors"
	"testing"
	"time"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// TestFetchTelemetrySuccess tests to make sure fetchTelemetry works on a mock
// vehicle.
func TestFetchTelemetrySuccess(t *testing.T) {
	want := telemetrypb.Telemetry_builder{Mode: modeP(telemetrypb.Mode_MODE_LOITER)}.Build()
	v := testVehicleContext(context.Background(), constantTelemetry(want))

	got, err := fetchTelemetry(v)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.GetMode() != want.GetMode() {
		t.Errorf("got mode %v, want %v", got.GetMode(), want.GetMode())
	}
}

// TestFetchTelemetryRPCError tests to make sure fetchTelemetry fails on a mock
// vehicle that returns an error.
func TestFetchTelemetryRPCError(t *testing.T) {
	v := testVehicleContext(context.Background(), failingTelemetry)

	_, err := fetchTelemetry(v)
	if !errors.Is(err, ErrInternal) {
		t.Fatalf("expected ErrInternal, got %v", err)
	}
}

// TestFetchTelemetrySuccess tests to make sure fetchTelemetry fails on a mock
// vehicle that has a missing telemetry payload.
func TestFetchTelemetryMissingPayload(t *testing.T) {
	empty := vehiclepb.GetTelemetryResponse_builder{}.Build()
	v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
		return empty, nil
	})

	_, err := fetchTelemetry(v)
	if !errors.Is(err, ErrInternal) {
		t.Fatalf("expected ErrInternal, got %v", err)
	}
}

// TestAnyMatches tests to make sure the anyMatches function correctly matches
// the contents of an Any with a protobuf message.
func TestAnyMatches(t *testing.T) {
	want := commonpb.GlobalPosition_builder{Latitude: f64(1), Longitude: f64(2)}.Build()

	t.Run("nil Any does not match", func(t *testing.T) {
		matches, err := anyMatches(nil, want)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if matches {
			t.Errorf("expected no match against a nil Any")
		}
	})

	t.Run("same type and content matches", func(t *testing.T) {
		same := commonpb.GlobalPosition_builder{Latitude: f64(1), Longitude: f64(2)}.Build()
		matches, err := anyMatches(mustAny(t, same), want)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !matches {
			t.Errorf("expected equal messages to match")
		}
	})

	t.Run("same type different content does not match", func(t *testing.T) {
		different := commonpb.GlobalPosition_builder{Latitude: f64(99), Longitude: f64(99)}.Build()
		matches, err := anyMatches(mustAny(t, different), want)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if matches {
			t.Errorf("expected differing content not to match")
		}
	})

	t.Run("different type does not match", func(t *testing.T) {
		otherType := commonpb.RelativePosition_builder{X: f32(1)}.Build()
		matches, err := anyMatches(mustAny(t, otherType), want)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if matches {
			t.Errorf("expected a different message type not to match")
		}
	})
}

// TestActionPollerImmediateMatch tests an action poller with an instant
// expectation match.
func TestActionPollerImmediateMatch(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tel := telemetrypb.Telemetry_builder{
		Mode:         modeP(telemetrypb.Mode_MODE_TAKEOFF),
		MotionStatus: motionStatusP(telemetrypb.MotionStatus_MOTION_STATUS_HOLDING),
	}.Build()
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := actionPoller(v, resp)(opt.WaitOptions{Timeout: time.Second})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestActionPollerModeMismatchCancels tests an action poller with a mode
// switch that persists past the stall window, which should result in an
// ErrCancelled.
func TestActionPollerModeMismatchCancels(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tel := telemetrypb.Telemetry_builder{
		Mode: modeP(telemetrypb.Mode_MODE_LAND), // a different command took over
	}.Build()
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := actionPoller(v, resp)(opt.WaitOptions{Timeout: time.Hour, Stall: 20 * time.Millisecond})
	if !errors.Is(err, ErrCancelled) {
		t.Fatalf("expected ErrCancelled, got %v", err)
	}
}

// TestActionPollerModeMismatchRecoversWithinStall tests that a mode mismatch
// which resolves before the stall window elapses.
func TestActionPollerModeMismatchRecoversWithinStall(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	calls := 0
	respond := func() (*vehiclepb.GetTelemetryResponse, error) {
		calls++
		mode := telemetrypb.Mode_MODE_LOITER
		status := telemetrypb.MotionStatus_MOTION_STATUS_HOLDING
		if calls > 1 {
			mode = telemetrypb.Mode_MODE_TAKEOFF
		}
		tel := telemetrypb.Telemetry_builder{Mode: modeP(mode), MotionStatus: motionStatusP(status)}.Build()
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
	}
	v := testVehicleContext(context.Background(), respond)

	err := actionPoller(v, resp)(opt.WaitOptions{Timeout: time.Second, Stall: time.Hour})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestActionPollerHonorsPollInterval tests that the poller paces its
// telemetry fetches to roughly w.Interval apart instead of busy-looping,
// by bounding how many fetches happen within a fixed timeout window.
func TestActionPollerHonorsPollInterval(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tel := telemetrypb.Telemetry_builder{
		Mode: modeP(telemetrypb.Mode_MODE_TAKEOFF),
	}.Build()
	calls := 0
	v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
		calls++
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
	})

	const (
		timeout  = 220 * time.Millisecond
		interval = 50 * time.Millisecond
	)
	err := actionPoller(v, resp)(opt.WaitOptions{Timeout: timeout, Interval: interval})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("expected ErrTimeout, got %v", err)
	}
	if calls > 10 {
		t.Fatalf("expected roughly timeout/interval fetches, got %d calls -- interval is not being honored", calls)
	}
}

// TestActionPollerTimeout tests an action poller with an expectation timeout.
func TestActionPollerTimeout(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	// Right mode but the vehicle never reaches the expected status
	tel := telemetrypb.Telemetry_builder{
		Mode:         modeP(telemetrypb.Mode_MODE_TAKEOFF),
		MotionStatus: motionStatusP(telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT),
	}.Build()
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := actionPoller(v, resp)(opt.WaitOptions{Timeout: 20 * time.Millisecond})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("expected ErrTimeout, got %v", err)
	}
}

// TestActionPollerZeroTimeoutNeverTimesOut tests that an action poller given
// the zero-value WaitOptions.Timeout doesn't time out.
func TestActionPollerZeroTimeoutNeverTimesOut(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	calls := 0
	respond := func() (*vehiclepb.GetTelemetryResponse, error) {
		calls++
		status := telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT
		if calls > 1 {
			status = telemetrypb.MotionStatus_MOTION_STATUS_HOLDING
		}
		tel := telemetrypb.Telemetry_builder{
			Mode:         modeP(telemetrypb.Mode_MODE_TAKEOFF),
			MotionStatus: motionStatusP(status),
		}.Build()
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
	}
	v := testVehicleContext(context.Background(), respond)

	err := actionPoller(v, resp)(opt.WaitOptions{}) // zero-value Timeout
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestActionPollerTimeout tests an action poller with a context timeout.
func TestActionPollerContextExpired(t *testing.T) {
	resp := driverpb.TakeOffResponse_builder{
		ExpectedMode:   telemetrypb.Mode_MODE_TAKEOFF,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	// Telemetry RPC itself is failing, so the poller can only observe the
	// cancellation, not a normal telemetry-based exit
	v := testVehicleContext(ctx, failingTelemetry)

	err := actionPoller(v, resp)(opt.WaitOptions{Timeout: 5 * time.Second})
	if !errors.Is(err, ErrContextExpired) {
		t.Fatalf("expected ErrContextExpired, got %v", err)
	}
}

// TestGuidancePollerImmediateMatch tests a guidance poller with an immediate
// expectation match.
func TestGuidancePollerImmediateMatch(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(1), Longitude: f64(1), Altitude: f32(10)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tol := opt.Tolerances{PosTol: 5}

	tel := telemetryForGuidance(setpoint, commonpb.GlobalPosition_builder{
		Latitude: f64(1), Longitude: f64(1), Altitude: f32(10),
	}.Build(), telemetrypb.MotionStatus_MOTION_STATUS_HOLDING)
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: time.Second, Tolerances: tol})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestGuidancePollerSetpointChangedCancels tests a guidance poller with a
// setpoint switch that persists past the stall window, which should result
// in an ErrCancelled.
func TestGuidancePollerSetpointChangedCancels(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(1), Longitude: f64(1)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()

	// The vehicle's current setpoint no longer matches ours: a newer
	// command must have superseded it
	otherSetpoint := commonpb.GlobalPosition_builder{Latitude: f64(99), Longitude: f64(99)}.Build()
	tel := telemetryForGuidance(otherSetpoint, otherSetpoint, telemetrypb.MotionStatus_MOTION_STATUS_HOLDING)
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: time.Hour, Stall: 20 * time.Millisecond})
	if !errors.Is(err, ErrCancelled) {
		t.Fatalf("expected ErrCancelled, got %v", err)
	}
}

// TestGuidancePollerSetpointRecoversWithinStall tests that a setpoint
// mismatch which resolves before the stall window elapses.
func TestGuidancePollerSetpointRecoversWithinStall(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(1), Longitude: f64(1)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tol := opt.Tolerances{PosTol: 5}

	oldSetpoint := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
	calls := 0
	respond := func() (*vehiclepb.GetTelemetryResponse, error) {
		calls++
		reported := oldSetpoint
		if calls > 1 {
			reported = setpoint
		}
		tel := telemetryForGuidance(reported, setpoint, telemetrypb.MotionStatus_MOTION_STATUS_HOLDING)
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
	}
	v := testVehicleContext(context.Background(), respond)

	err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: time.Second, Stall: time.Hour, Tolerances: tol})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestGuidancePollerTimeout tests a guidance poller with an expectation timeout.
func TestGuidancePollerTimeout(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tol := opt.Tolerances{PosTol: 1}

	// Far from the setpoint, but making steady one-way progress each call
	// so the stall detector never trips before the timeout does
	start := time.Now()
	v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
		// Distance shrinks with elapsed time but never gets remotely close
		// within the short timeout used below
		lat := 1.0 - float64(time.Since(start))/float64(time.Second)*0.0000001
		actual := commonpb.GlobalPosition_builder{Latitude: f64(lat), Longitude: f64(0)}.Build()
		tel := telemetryForGuidance(setpoint, actual, telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT)
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
	})

	err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: 20 * time.Millisecond, Stall: time.Hour, Tolerances: tol})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("expected ErrTimeout, got %v", err)
	}
}

// TestGuidancePollerStallDetected tests a guidance poller with a stall
// timeout; this means that the command is not progressing towards the goal.
// It also tests that once a stall is armed, resumed progress resets the
// timer, so a later stall still gets caught rather than being masked by the
// first one.
func TestGuidancePollerStallDetected(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(1), Longitude: f64(0)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tol := opt.Tolerances{PosTol: 1}

	t.Run("no progress trips the stall timer", func(t *testing.T) {
		// The vehicle reports the correct setpoint but never actually moves,
		// so distance never improves between polls
		actual := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
		tel := telemetryForGuidance(setpoint, actual, telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT)
		v := testVehicleContext(context.Background(), constantTelemetry(tel))

		err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: time.Hour, Stall: 20 * time.Millisecond, Tolerances: tol})
		if !errors.Is(err, ErrFailedExpectation) {
			t.Fatalf("expected ErrFailedExpectation, got %v", err)
		}
	})

	t.Run("progress resets the stall timer", func(t *testing.T) {
		const (
			stalledPhase  = 15 * time.Millisecond // long enough to arm the stall timer, short enough not to fire it
			progressPhase = 15 * time.Millisecond // continuous progress here must reset the timer
			stall         = 20 * time.Millisecond
		)

		// Three phases driven off wall-clock time: parked (arms the stall
		// timer), then steady progress (must reset it), then parked again
		// (a fresh stall that should still get caught)
		start := time.Now()
		v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
			elapsed := time.Since(start)
			var lat float64
			switch {
			case elapsed < stalledPhase:
				lat = 0 // parked far from the setpoint
			case elapsed < stalledPhase+progressPhase:
				// Steadily close the distance so every poll in this window
				// looks like progress and resets the stall timer
				frac := float64(elapsed-stalledPhase) / float64(progressPhase)
				lat = 0.001 * frac
			default:
				lat = 0.001 // parked again, closer but still nowhere near tolerance
			}
			actual := commonpb.GlobalPosition_builder{Latitude: f64(lat), Longitude: f64(0)}.Build()
			tel := telemetryForGuidance(setpoint, actual, telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT)
			return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
		})

		err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: 500 * time.Millisecond, Stall: stall, Tolerances: tol})
		elapsed := time.Since(start)
		if !errors.Is(err, ErrFailedExpectation) {
			t.Fatalf("expected ErrFailedExpectation once the second stall completes, got %v (after %v)", err, elapsed)
		}
		// The second stall can't complete before the progress phase ends
		// plus another Stall duration; finishing any earlier means the
		// first stall's timer fired instead of a fresh one armed by the
		// post-progress stall
		if minElapsed := stalledPhase + progressPhase + stall/2; elapsed < minElapsed {
			t.Errorf("stall fired too early (after %v); wanted at least %v since a fresh stall timer should only start once progress stops", elapsed, minElapsed)
		}
	})

	t.Run("oscillating distance still trips the stall timer", func(t *testing.T) {
		// Distance alternates between two values that never improve on the
		// best one seen (e.g. GPS noise around a plateau well outside
		// tolerance)
		lats := []float64{0.010, 0.009, 0.010, 0.009, 0.010, 0.009, 0.010, 0.009, 0.010, 0.009}
		call := 0
		v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
			lat := lats[call%len(lats)]
			call++
			actual := commonpb.GlobalPosition_builder{Latitude: f64(lat), Longitude: f64(0)}.Build()
			tel := telemetryForGuidance(setpoint, actual, telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT)
			return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
		})

		err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: time.Hour, Stall: 30 * time.Millisecond, Interval: time.Millisecond, Tolerances: tol})
		if !errors.Is(err, ErrFailedExpectation) {
			t.Fatalf("expected ErrFailedExpectation, got %v", err)
		}
	})
}

// TestGuidancePollerStallDetectedAtZeroDistance tests that reaching the
// setpoint exactly (distance == 0.0) doesn't permanently disable the stall
// detector.
func TestGuidancePollerStallDetectedAtZeroDistance(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	tol := opt.Tolerances{PosTol: 1}

	tel := telemetryForGuidance(setpoint, setpoint, telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT)
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: time.Second, Stall: 20 * time.Millisecond, Tolerances: tol})
	if !errors.Is(err, ErrFailedExpectation) {
		t.Fatalf("expected ErrFailedExpectation, got %v", err)
	}
}

// TestGuidancePollerContextExpired tests a guidance poller with a context
// timeout.
func TestGuidancePollerContextExpired(t *testing.T) {
	setpoint := commonpb.GlobalPosition_builder{Latitude: f64(0), Longitude: f64(0)}.Build()
	resp := driverpb.SetGlobalPositionTargetResponse_builder{
		Setpoint:       setpoint,
		ExpectedStatus: telemetrypb.MotionStatus_MOTION_STATUS_HOLDING,
	}.Build()
	actual := commonpb.GlobalPosition_builder{Latitude: f64(50), Longitude: f64(50)}.Build()
	tel := telemetryForGuidance(setpoint, actual, telemetrypb.MotionStatus_MOTION_STATUS_IN_TRANSIT)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	v := testVehicleContext(ctx, constantTelemetry(tel))

	err := guidancePoller(v, resp)(opt.WaitOptions{Timeout: 5 * time.Second, Stall: time.Hour})
	if !errors.Is(err, ErrContextExpired) {
		t.Fatalf("expected ErrContextExpired, got %v", err)
	}
}

// TestGimbalPollerImmediateMatch tests a gimbal poller with an immediate
// expectation match.
func TestGimbalPollerImmediateMatch(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(10), Yaw: f32(90)}.Build()
	resp := driverpb.SetGimbalAngleTargetResponse_builder{Setpoint: setpoint}.Build()
	tol := opt.Tolerances{AngleTol: 3}

	tel := telemetryForGimbal(setpoint, commonpb.Pose_builder{Pitch: f32(10), Yaw: f32(90)}.Build())
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := gimbalPoller(v, resp)(opt.WaitOptions{Timeout: time.Second, Tolerances: tol})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestGimbalPollerSetpointChangedCancels tests a gimbal poller with a
// setpoint switch that persists past the stall window, which should result
// in an ErrCancelled.
func TestGimbalPollerSetpointChangedCancels(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(10)}.Build()
	resp := driverpb.SetGimbalAngleTargetResponse_builder{Setpoint: setpoint}.Build()

	otherSetpoint := commonpb.Pose_builder{Pitch: f32(80)}.Build()
	tel := telemetryForGimbal(otherSetpoint, otherSetpoint)
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := gimbalPoller(v, resp)(opt.WaitOptions{Timeout: time.Hour, Stall: 20 * time.Millisecond})
	if !errors.Is(err, ErrCancelled) {
		t.Fatalf("expected ErrCancelled, got %v", err)
	}
}

// TestGimbalPollerSetpointRecoversWithinStall tests that a setpoint mismatch
// which resolves before the stall window elapses.
func TestGimbalPollerSetpointRecoversWithinStall(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(10)}.Build()
	resp := driverpb.SetGimbalAngleTargetResponse_builder{Setpoint: setpoint}.Build()
	tol := opt.Tolerances{AngleTol: 3}

	oldSetpoint := commonpb.Pose_builder{Pitch: f32(0)}.Build()
	calls := 0
	respond := func() (*vehiclepb.GetTelemetryResponse, error) {
		calls++
		reported := oldSetpoint
		if calls > 1 {
			reported = setpoint
		}
		tel := telemetryForGimbal(reported, setpoint)
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: tel}.Build(), nil
	}
	v := testVehicleContext(context.Background(), respond)

	err := gimbalPoller(v, resp)(opt.WaitOptions{Timeout: time.Second, Stall: time.Hour, Tolerances: tol})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// TestGimbalPollerTimeout tests a gimbal poller with an expectation timeout.
func TestGimbalPollerTimeout(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(10)}.Build()
	resp := driverpb.SetGimbalAngleTargetResponse_builder{Setpoint: setpoint}.Build()
	tol := opt.Tolerances{AngleTol: 1}

	actual := commonpb.Pose_builder{Pitch: f32(90)}.Build() // stays far away
	tel := telemetryForGimbal(setpoint, actual)
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := gimbalPoller(v, resp)(opt.WaitOptions{Timeout: 20 * time.Millisecond, Stall: time.Hour, Tolerances: tol})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("expected ErrTimeout, got %v", err)
	}
}

// TestGimbalPollerStallDetected tests a gimbal poller with a stall timeout;
// this means that the command is not progressing towards the goal.
func TestGimbalPollerStallDetected(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(10)}.Build()
	resp := driverpb.SetGimbalAngleTargetResponse_builder{Setpoint: setpoint}.Build()
	tol := opt.Tolerances{AngleTol: 1}

	actual := commonpb.Pose_builder{Pitch: f32(90)}.Build() // never moves
	tel := telemetryForGimbal(setpoint, actual)
	v := testVehicleContext(context.Background(), constantTelemetry(tel))

	err := gimbalPoller(v, resp)(opt.WaitOptions{Timeout: time.Hour, Stall: 20 * time.Millisecond, Tolerances: tol})
	if !errors.Is(err, ErrFailedExpectation) {
		t.Fatalf("expected ErrFailedExpectation, got %v", err)
	}
}

// TestGimbalPollerContextExpired tests a gimbal poller with a context
// timeout.
func TestGimbalPollerContextExpired(t *testing.T) {
	setpoint := commonpb.Pose_builder{Pitch: f32(10)}.Build()
	resp := driverpb.SetGimbalAngleTargetResponse_builder{Setpoint: setpoint}.Build()
	actual := commonpb.Pose_builder{Pitch: f32(90)}.Build()
	tel := telemetryForGimbal(setpoint, actual)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	v := testVehicleContext(ctx, constantTelemetry(tel))

	err := gimbalPoller(v, resp)(opt.WaitOptions{Timeout: 5 * time.Second, Stall: time.Hour})
	if !errors.Is(err, ErrContextExpired) {
		t.Fatalf("expected ErrContextExpired, got %v", err)
	}
}
