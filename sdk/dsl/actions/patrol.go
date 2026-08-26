package actions

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/geo"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// PatrolMode represents the types of patrol patterns that can be
// executed.
type PatrolMode uint32

const (
	PatrolModeCorridor PatrolMode = iota // corridor scan around the exterior
	PatrolModeSurvey                     // survey over the interior
)

// Patrol orders the vehicle to visit the waypoints on a
type Patrol struct {
	Area          params.MapFeature // polygon to patrol around
	Altitude      float32           // altitude for each point in patrol
	mode          PatrolMode        // mode for patrol, either survey or corridor (corridor by default)
	spacing       float32           // survey spacing (default to 10.0m, only used in survey mode)
	heading       float32           // survey heading (default to 0.0deg, only used in survey mode)
	PatrolOptions []opt.Option[*Patrol]
	MoveOptions   []opt.Option[opt.SetGlobalPositionTargetOption]
}

func (p *Patrol) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	p.mode = PatrolModeCorridor
	p.spacing = 10.0
	p.heading = 0.0
	for _, opt := range p.PatrolOptions {
		opt(p)
	}
	var err error
	var points []geo.GeoPoint
	if p.mode == PatrolModeCorridor {
		points, err = m.Map.CorridorScan(p.Area, p.Altitude)
	} else {
		points, err = m.Map.SurveyScan(p.Area, p.spacing, p.heading, p.Altitude)
	}
	if err != nil {
		return err
	}

	for _, n := range points {
		_, err = v.SetGlobalPositionTarget(
			n.Latitude,
			n.Longitude,
			n.Altitude,
			n.Heading,
			p.MoveOptions...,
		).Wait()
		if err != nil {
			return err
		}
	}
	return nil
}

// WithPatrolMode sets the optional patrol mode.
func WithPatrolMode(mode PatrolMode) func(*Patrol) {
	return func(p *Patrol) {
		p.mode = mode
	}
}

// WithPatrolSpacing sets the spacing for the survey scan (default to 10.0m).
func WithPatrolSpacing(spacing float32) func(*Patrol) {
	return func(p *Patrol) {
		p.spacing = spacing
	}
}

// WithPatrolHeading sets the heading for the survey scan (default to 0.0deg).
func WithPatrolHeading(heading float32) func(*Patrol) {
	return func(p *Patrol) {
		p.heading = heading
	}
}

var _ dsl.Action = &Patrol{}
