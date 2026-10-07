// Package fixtures holds small, self-contained DSL types for linker_test.go
// and render_test.go to link and render against. It is kept separate from
// any package a real mission would compile against, so that adding a case
// here can't accidentally change real missions.
package fixtures

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// Mode is a uint32-backed fixture enum.
type Mode uint32

const (
	ModeIdle Mode = iota
	ModeActive
)

// Label is a string-backed fixture enum.
type Label string

const (
	LabelHome Label = "home"
	LabelAway Label = "away"
)

// Waypoint is a fixture Datatype with two required fields and an optional
// one without a default.
type Waypoint struct {
	Lat float64
	Lon float64
	// #optional
	Name string
}

func (*Waypoint) Type() {}

var _ dsl.Datatype = &Waypoint{}

// Route is a fixture Datatype which nests another Datatype, both directly
// and in a slice, to exercise recursive linking and rendering.
type Route struct {
	Start Waypoint
	// #optional
	Stops []Waypoint
}

func (*Route) Type() {}

var _ dsl.Datatype = &Route{}

// Hover is a fixture Action with no fields.
type Hover struct{}

func (*Hover) Execute(v sdk.Vehicle, m dsl.MissionData) error { return nil }

var _ dsl.Action = &Hover{}

// Fly is a fixture Action with one required field and an optional field of
// every kind of value the DSL can express, some of which have defaults.
type Fly struct {
	Speed float32
	// #optional
	Count int32
	// #optional
	Note string
	// #optional
	Mode Mode
	// #optional
	Enabled bool
	// #optional
	Points []float64
	// #optional
	Target *Waypoint
	// #optional
	Route Route
	// #optional[3.0]
	Timeout float32
	// #optional[ModeActive]
	Fallback Mode
	// #optional[home]
	Tag Label
}

func (*Fly) Execute(v sdk.Vehicle, m dsl.MissionData) error { return nil }

var _ dsl.Action = &Fly{}

// Seen is a fixture Event with no fields.
type Seen struct{}

func (*Seen) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) { return false, nil }

var _ dsl.Event = &Seen{}
