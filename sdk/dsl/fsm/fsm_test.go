package fsm

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// TestStartRunsActionsThroughDoneToTerminalAction checks that Start drives
// the mission from its start action through a "done" transition into a
// terminal action (one with no declared transitions), returning nil once
// that terminal action's Execute call finishes without error.
func TestStartRunsActionsThroughDoneToTerminalAction(t *testing.T) {
	var aRan, bRan bool
	actions := map[string]dsl.Action{
		"a": &fakeAction{execute: func(v sdk.Vehicle) error { aRan = true; return nil }},
		"b": &fakeAction{execute: func(v sdk.Vehicle) error { bRan = true; return nil }},
	}
	transitions := map[string]map[string]string{"a": {"done": "b"}}
	d := NewDslFsm("a", transitions, actions, nil, dsl.MissionData{}, nil)

	if err := d.Start(context.Background()); err != nil {
		t.Fatalf("Start() = %v, want nil", err)
	}
	if !aRan || !bRan {
		t.Fatalf("aRan=%v bRan=%v, want both true", aRan, bRan)
	}
}

// TestStartFiresTransitionOnEventMonitor checks that when an event's
// Monitor call returns true, the FSM fires that event's transition and
// cancels the context of the action still racing against it.
func TestStartFiresTransitionOnEventMonitor(t *testing.T) {
	aCancelled := make(chan struct{})
	actions := map[string]dsl.Action{
		"a": &fakeAction{execute: func(v sdk.Vehicle) error {
			<-v.Ctx().Done()
			close(aCancelled)
			return v.Ctx().Err()
		}},
		"b": &fakeAction{execute: func(v sdk.Vehicle) error { return nil }},
	}
	events := map[string]dsl.Event{
		"seen": &fakeEvent{monitor: func(v sdk.Vehicle) (bool, error) { return true, nil }},
	}
	transitions := map[string]map[string]string{"a": {"seen": "b"}}
	d := NewDslFsm("a", transitions, actions, events, dsl.MissionData{}, nil)

	if err := d.Start(context.Background()); err != nil {
		t.Fatalf("Start() = %v, want nil", err)
	}
	select {
	case <-aCancelled:
	case <-time.After(time.Second):
		t.Fatal("action a's context was never cancelled after event \"seen\" won the race")
	}
}

// TestStartReturnsActionExecuteError checks that an error from an action's
// Execute call aborts the mission and is returned from Start.
func TestStartReturnsActionExecuteError(t *testing.T) {
	wantErr := errors.New("boom")
	actions := map[string]dsl.Action{
		"a": &fakeAction{execute: func(v sdk.Vehicle) error { return wantErr }},
	}
	d := NewDslFsm("a", nil, actions, nil, dsl.MissionData{}, nil)

	err := d.Start(context.Background())
	if !errors.Is(err, wantErr) {
		t.Fatalf("Start() = %v, want error wrapping %v", err, wantErr)
	}
}

// TestStartReturnsEventMonitorError checks that an error from an event's
// Monitor call aborts the mission and is returned from Start.
func TestStartReturnsEventMonitorError(t *testing.T) {
	wantErr := errors.New("boom")
	actions := map[string]dsl.Action{
		"a": &fakeAction{execute: func(v sdk.Vehicle) error {
			<-v.Ctx().Done()
			return v.Ctx().Err()
		}},
	}
	events := map[string]dsl.Event{
		"seen": &fakeEvent{monitor: func(v sdk.Vehicle) (bool, error) { return false, wantErr }},
	}
	transitions := map[string]map[string]string{"a": {"seen": "b"}}
	d := NewDslFsm("a", transitions, actions, events, dsl.MissionData{}, nil)

	err := d.Start(context.Background())
	if !errors.Is(err, wantErr) {
		t.Fatalf("Start() = %v, want error wrapping %v", err, wantErr)
	}
}

// TestStartEndsMissionWhenDoneHasNoMatchingRule checks that when an
// action's Execute call finishes but the current state has no "done" rule
// (only an event rule that never fires), the mission ends normally instead
// of hanging forever waiting on the event.
func TestStartEndsMissionWhenDoneHasNoMatchingRule(t *testing.T) {
	actions := map[string]dsl.Action{
		"a": &fakeAction{execute: func(v sdk.Vehicle) error { return nil }},
	}
	events := map[string]dsl.Event{
		"seen": &fakeEvent{monitor: func(v sdk.Vehicle) (bool, error) {
			<-v.Ctx().Done()
			return false, nil
		}},
	}
	transitions := map[string]map[string]string{"a": {"seen": "b"}}
	d := NewDslFsm("a", transitions, actions, events, dsl.MissionData{}, nil)

	done := make(chan error, 1)
	go func() { done <- d.Start(context.Background()) }()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Start() = %v, want nil", err)
		}
	case <-time.After(time.Second):
		t.Fatal(`Start did not return promptly when the action finished with no matching "done" rule`)
	}
}
