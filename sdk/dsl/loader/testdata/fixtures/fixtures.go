// Package fixtures holds small, self-contained DSL types for
// loader_test.go to load with LoadTypes. It is kept separate from any
// package the loader would ever load for real so that adding a case here
// can't accidentally change what a real mission compiles against.
package fixtures

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// Hover is a fixture Action with one required and one optional field, used
// to exercise field/comment/optional-tag extraction.
type Hover struct {
	// Duration is how long to hover, in seconds.
	Duration float32
	// #optional
	Altitude float32 // meters above ground
}

func (h *Hover) Execute(v sdk.Vehicle, m dsl.MissionData) error { return nil }

var _ dsl.Action = &Hover{}

// Seen is a fixture Event with no fields.
type Seen struct{}

func (s *Seen) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) { return false, nil }

var _ dsl.Event = &Seen{}

// Waypoint is a fixture Datatype.
type Waypoint struct {
	Lat float64
	Lon float64
}

func (w *Waypoint) Type() {}

var _ dsl.Datatype = &Waypoint{}

// Plain implements none of Action, Event, or Datatype, and should be
// skipped entirely by LoadTypes.
type Plain struct {
	X int
}

// Mode enumerates fixture flight modes.
type Mode uint32

const (
	// ModeIdle is the default, do-nothing mode.
	ModeIdle   Mode = iota
	ModeActive      // mode entered once a mission starts moving
)
