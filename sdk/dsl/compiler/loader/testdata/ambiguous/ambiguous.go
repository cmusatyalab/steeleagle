// Package ambiguous holds a single fixture type that implements more than
// one of dsl.Action/Event/Datatype, kept apart from testdata/fixtures so
// that loading it doesn't also fail every other fixture-based test with
// the ambiguous-interface compile error it exists to trigger.
package ambiguous

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// Ambiguous implements both Action and Event at once, which LoadTypes
// should report as a compile error instead of registering under either.
type Ambiguous struct{}

func (a *Ambiguous) Execute(v sdk.Vehicle, m dsl.MissionData) error { return nil }

func (a *Ambiguous) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) { return false, nil }
