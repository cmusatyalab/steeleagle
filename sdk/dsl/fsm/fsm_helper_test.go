package fsm

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// fakeAction is a dsl.Action test double whose Execute behavior is supplied
// by the test.
type fakeAction struct {
	execute func(v sdk.Vehicle) error
}

func (f *fakeAction) Execute(v sdk.Vehicle, _ dsl.MissionData) error { return f.execute(v) }

// fakeEvent is a dsl.Event test double whose Monitor behavior is supplied
// by the test.
type fakeEvent struct {
	monitor func(v sdk.Vehicle) (bool, error)
}

func (f *fakeEvent) Monitor(v sdk.Vehicle, _ dsl.MissionData) (bool, error) { return f.monitor(v) }
