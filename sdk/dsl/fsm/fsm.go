package fsm

import (
	"context"
	"fmt"
	"sync"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/looplab/fsm"
	"google.golang.org/grpc"
)

// doneEvent is the synthetic event name raised when an action's Execute
// call returns without error. Every action implicitly raises it on
// completion whether or not the mission declares a rule for it. If it is
// triggered with no transition target, the mission ends.
const doneEvent = "done"

// DslFsm executes a compiled DSL mission as a finite state machine,
// built with looplab/fsm.
type DslFsm struct {
	fsm         *fsm.FSM
	transitions map[string]map[string]string // action -> event -> next action
	actions     map[string]dsl.Action
	events      map[string]dsl.Event
	data        dsl.MissionData
	conn        *grpc.ClientConn
	rootCtx     context.Context // set by Start; scopes every action/event call for the whole mission
	doneOnce    sync.Once
	done        chan error
}

// NewDslFsm creates a DSL runtime for a mission compiled to transitions,
// actions, and events, that dials out to the vehicle over conn. data is
// passed to every action's Execute call and every event's Monitor call. Call
// Start to begin executing the mission from its start action.
func NewDslFsm(
	start string,
	transitions map[string]map[string]string,
	actions map[string]dsl.Action,
	events map[string]dsl.Event,
	data dsl.MissionData,
	conn *grpc.ClientConn,
) *DslFsm {
	d := &DslFsm{
		transitions: transitions,
		actions:     actions,
		events:      events,
		data:        data,
		conn:        conn,
		done:        make(chan error, 1),
	}
	d.fsm = fsm.NewFSM(start, fsmEvents(transitions), fsm.Callbacks{
		"enter_state": func(_ context.Context, e *fsm.Event) {
			d.data.Log.Info().Str("from", e.Src).Str("to", e.Dst).Str("event", e.Event).Msg("state transition")
			d.enterState(e.Dst)
		},
	})
	return d
}

// fsmEvents flattens transitions into looplab/fsm's EventDesc form: one
// EventDesc per (action, event) rule, sourced from the action the rule is
// declared under and destined for the action it names.
func fsmEvents(transitions map[string]map[string]string) []fsm.EventDesc {
	var descs []fsm.EventDesc
	for action, rules := range transitions {
		for event, next := range rules {
			descs = append(descs, fsm.EventDesc{Name: event, Src: []string{action}, Dst: next})
		}
	}
	return descs
}

// Start begins mission execution at the FSM's start action and blocks until
// the mission reaches a terminal action (one whose Execute call finishes
// without error and has no matching "done" rule) or an action or event
// reports an error.
func (d *DslFsm) Start(ctx context.Context) error {
	d.rootCtx = ctx
	d.data.Log.Info().Str("state", d.fsm.Current()).Msg("mission started")
	d.enterState(d.fsm.Current())
	return <-d.done
}

// finish records the mission's outcome, signaling Start. Only the first call
// has any effect.
func (d *DslFsm) finish(err error) {
	d.doneOnce.Do(func() { d.done <- err })
}

// enterState runs state's action and races it against Monitor calls for
// every event state can transition on: whichever resolves first (the
// action completing, matched against a "done" rule if one exists, or an
// event's Monitor call returning true) fires the corresponding transition,
// cancelling every other in-flight call for this state.
func (d *DslFsm) enterState(state string) {
	action, ok := d.actions[state]
	if !ok {
		d.finish(fmt.Errorf("no action registered for state %q", state))
		return
	}

	stateCtx, cancel := context.WithCancel(d.rootCtx)
	rules := d.transitions[state] // nil for a terminal action, no outgoing rules

	// resolveOnce ensures exactly one of this state's racing action/event
	// calls decides its outcome
	var resolveOnce sync.Once
	transition := func(name string) {
		resolveOnce.Do(func() {
			cancel()
			d.fireEvent(state, name)
		})
	}
	abort := func(err error) {
		resolveOnce.Do(func() {
			cancel()
			d.finish(err)
		})
	}

	go func() {
		vehicle := sdk.NewVehicleFromContext(stateCtx, d.conn)
		if err := action.Execute(vehicle, d.data); err != nil {
			abort(fmt.Errorf("action %q: %w", state, err))
			return
		}
		transition(doneEvent)
	}()

	for name, next := range rules {
		if name == doneEvent {
			continue
		}
		event, ok := d.events[name]
		if !ok {
			abort(fmt.Errorf("no event registered for %q -> %q from state %q", name, next, state))
			continue
		}
		go func(name string, event dsl.Event) {
			vehicle := sdk.NewVehicleFromContext(stateCtx, d.conn)
			ok, err := event.Monitor(vehicle, d.data)
			if err != nil {
				abort(fmt.Errorf("event %q: %w", name, err))
				return
			}
			if ok {
				transition(name)
			}
		}(name, event)
	}
}

// fireEvent fires name on the underlying FSM from state. When name is the
// synthetic "done" event and state has no matching rule for it, that means
// state is a terminal action, so the mission has completed normally rather
// than failed. Any other error firing the event aborts the mission.
func (d *DslFsm) fireEvent(state, name string) {
	err := d.fsm.Event(context.Background(), name)
	if err == nil {
		return
	}
	if name == doneEvent {
		switch err.(type) {
		case fsm.InvalidEventError, fsm.UnknownEventError:
			d.finish(nil)
			return
		}
	}
	d.finish(fmt.Errorf("firing %q from %q: %w", name, state, err))
}
