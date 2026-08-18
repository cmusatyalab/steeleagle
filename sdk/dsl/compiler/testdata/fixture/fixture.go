// Package fixture provides small, real DSL types (a Datatype, an Action, and
// an Event) for dsl/compiler tests to link and generate against, exercising
// literal fields, inline constructors, cross-references, arrays, and
// functional options without depending on any real vehicle package.
package fixture

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// Waypoint is a fixture Datatype with plain literal fields.
type Waypoint struct {
	Alt  float64
	Area string
}

func (*Waypoint) Type() {}

var _ dsl.Datatype = &Waypoint{}

// PatrolOption is a fixture functional-option constraint for Patrol.
type PatrolOption interface {
	SetSpeed(float32)
}

// WithSpeed sets Patrol's cruise speed.
func WithSpeed(v float32) opt.Option[PatrolOption] {
	return func(o PatrolOption) { o.SetSpeed(v) }
}

// Patrol is a fixture Action exercising a plain field referencing another
// declared value (Home), an array field (Waypoints), and an option (Speed).
type Patrol struct {
	Home      *Waypoint
	Waypoints []*Waypoint
	Options   []opt.Option[PatrolOption]
}

func (p *Patrol) Execute(v sdk.Vehicle) error { return nil }

var _ dsl.Action = &Patrol{}

// Timer is a fixture Event exercising a plain literal field.
type Timer struct {
	Seconds int64
}

func (t *Timer) Monitor(v sdk.Vehicle) (bool, error) { return true, nil }

var _ dsl.Event = &Timer{}
