package vehicle

import (
	"errors"
	"fmt"
	"strings"
	"testing"
	"time"

	missionpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/mission"
	"google.golang.org/grpc/codes"
)

// startMission starts the loaded mission of v.
func startMission(t *testing.T, v *Vehicle) error {
	t.Helper()
	_, err := missionpb.NewMissionServiceClient(v.conn).StartMission(callCtx(t), &missionpb.StartMissionRequest{})
	return err
}

// stopMission stops the running mission of v.
func stopMission(t *testing.T, v *Vehicle) error {
	t.Helper()
	_, err := missionpb.NewMissionServiceClient(v.conn).StopMission(callCtx(t), &missionpb.StopMissionRequest{})
	return err
}

// TestStartStopMission checks that a loaded mission can be started and
// stopped repeatedly, and that it can't be started twice or replaced while it
// runs.
func TestStartStopMission(t *testing.T) {
	v, _ := newTestVehicle(t)
	expectCode(t, startMission(t, v), codes.FailedPrecondition, "no mission")
	expectCode(t, stopMission(t, v), codes.FailedPrecondition, "no mission")
	installMission(t, v, "idle")
	if err := loadMission(t, v, "idle"); err != nil {
		t.Fatal(err)
	}

	for i := range 2 {
		if err := startMission(t, v); err != nil {
			t.Fatalf("start %d: %v", i, err)
		}
		if !v.mission.Running() {
			t.Fatalf("start %d: mission isn't running", i)
		}
		expectCode(t, startMission(t, v), codes.FailedPrecondition, "already running")
		expectCode(t, loadMission(t, v, "idle"), codes.FailedPrecondition, "running")
		if err := stopMission(t, v); err != nil {
			t.Fatalf("stop %d: %v", i, err)
		}
		if v.mission.Running() || v.missionInfo != nil {
			t.Fatalf("stop %d: mission still running", i)
		}
	}
	// Stopping a stopped mission does nothing
	if err := stopMission(t, v); err != nil {
		t.Error(err)
	}
}

// missionStartedMarker is what the test mission writes to stderr once its
// StartMission is called, matching its StartedMarker.
const missionStartedMarker = "test mission started"

// missionStoppedMarker is what the test mission writes to stderr when its
// StopMission is called, matching its StoppedMarker.
const missionStoppedMarker = "test mission stopped"

// expectOutputCount waits until out holds n of marker.
func expectOutputCount(t *testing.T, out *syncBuffer, marker string, n int) {
	t.Helper()
	eventually(t, 5*time.Second, func() error {
		if got := strings.Count(out.String(), marker); got != n {
			return fmt.Errorf("output holds %d of %q, want %d; output:\n%s", got, marker, n, out.String())
		}
		return nil
	})
}

// TestStartMissionStartsMission checks that starting a mission relays
// StartMission to the launched mission process, which does nothing until it is
// called, that stopping it relays StopMission before it is killed, and that
// the mission's output is written to the vehicle's process output stream.
func TestStartMissionStartsMission(t *testing.T) {
	out := &syncBuffer{}
	v, _ := newTestVehicle(t, WithProcessOutputStream(out))
	installMission(t, v, "idle")
	if err := loadMission(t, v, "idle"); err != nil {
		t.Fatal(err)
	}
	for i := range 2 {
		if err := startMission(t, v); err != nil {
			t.Fatalf("start %d: %v", i, err)
		}
		expectOutputCount(t, out, missionStartedMarker, i+1)
		if err := stopMission(t, v); err != nil {
			t.Fatalf("stop %d: %v", i, err)
		}
		expectOutputCount(t, out, missionStoppedMarker, i+1)
	}
}

// TestStopMissionKillsStuckMission checks that a mission whose StopMission
// doesn't return is killed once the stop timeout passes.
func TestStopMissionKillsStuckMission(t *testing.T) {
	out := &syncBuffer{}
	v, _ := newTestVehicle(t, WithProcessOutputStream(out))
	installMission(t, v, "stuck")
	if err := loadMission(t, v, "stuck"); err != nil {
		t.Fatal(err)
	}
	if err := startMission(t, v); err != nil {
		t.Fatal(err)
	}
	if err := stopMission(t, v); err != nil {
		t.Fatal(err)
	}
	expectOutputCount(t, out, missionStoppedMarker, 1)
	if v.mission.Running() || v.missionInfo != nil {
		t.Fatal("stuck mission still running")
	}
}

// TestStartMissionRejected checks that a mission whose StartMission fails
// fails the vehicle's StartMission with its error, and is stopped so it can
// be started again.
func TestStartMissionRejected(t *testing.T) {
	v, _ := newTestVehicle(t)
	installMission(t, v, "reject")
	if err := loadMission(t, v, "reject"); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		expectCode(t, startMission(t, v), codes.Aborted, "rejected")
		if v.mission.Running() || v.missionInfo != nil {
			t.Fatal("rejected mission still running")
		}
	}
}

// TestMissionCallsVehicle checks that a started mission can call the
// vehicle's services, and that a mission that exited can be started again.
func TestMissionCallsVehicle(t *testing.T) {
	v, _ := newTestVehicle(t)
	installMission(t, v, "callback")
	if err := loadMission(t, v, "callback"); err != nil {
		t.Fatal(err)
	}
	for i := range 2 {
		if err := startMission(t, v); err != nil {
			t.Fatalf("start %d: %v", i, err)
		}
		// The mission makes its call when it is started, and exits
		// successfully once it succeeds
		done := make(chan error, 1)
		go func() { done <- v.mission.Wait() }()
		select {
		case err := <-done:
			if err != nil {
				t.Fatalf("run %d: mission failed: %v", i, err)
			}
		case <-time.After(10 * time.Second):
			t.Fatalf("run %d: mission didn't exit", i)
		}
	}
	if err := stopMission(t, v); err != nil {
		t.Error(err)
	}
}

// TestMissionStopsWithVehicle checks that a running mission is stopped when
// the vehicle's run is.
func TestMissionStopsWithVehicle(t *testing.T) {
	v, _ := newTestVehicle(t)
	installMission(t, v, "idle")
	if err := loadMission(t, v, "idle"); err != nil {
		t.Fatal(err)
	}
	if err := startMission(t, v); err != nil {
		t.Fatal(err)
	}
	v.cancel()
	eventually(t, 10*time.Second, func() error {
		if v.mission.Running() {
			return errors.New("mission still running")
		}
		return nil
	})
}
