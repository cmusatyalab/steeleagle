package actions

import (
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
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
	Area     params.MapFeature // polygon to patrol around
	Altitude float32           // altitude for each point in patrol
	// #optional
	AltitudeMode enums.AltitudeMode // how to interpret altitude, MSL or above take off
	// #optional
	Pattern PatrolMode // mode for patrol, either survey or corridor (corridor by default)
	// #optional[10.0]
	SurveySpacing float32 // survey spacing (default to 10.0m, only used in survey mode)
	// #optional
	SurveyHeading float32 // survey heading (default to 0.0deg, only used in survey mode)
	// #optional[3.0]
	Speed float32
	// #optional[120.0]
	AngularSpeed float32
}

func (p *Patrol) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	var err error
	var points []geo.GeoPoint
	if p.Pattern == PatrolModeCorridor {
		points, err = m.Map.CorridorScan(p.Area, p.Altitude)
	} else {
		points, err = m.Map.SurveyScan(p.Area, p.SurveySpacing, p.SurveyHeading, p.Altitude)
	}
	if err != nil {
		return err
	}

	options := []opt.Option[opt.SetGlobalPositionTargetOption]{}
	options = append(options, opt.WithAltitudeMode[opt.SetGlobalPositionTargetOption](p.AltitudeMode))
	// #exclude-ifndef services/driver/SetGlobalPositionTargetRequest/speed
	options = append(options, opt.WithSpeed[opt.SetGlobalPositionTargetOption](p.Speed))
	// #exclude-ifndef services/driver/SetGlobalPositionTargetRequest/angular_speed
	options = append(options, opt.WithAngularSpeed[opt.SetGlobalPositionTargetOption](p.AngularSpeed))
	for i, n := range points {
		m.Log.Info().Msgf("transiting to waypoint %d / %d", i, len(points))
		_, err = v.SetGlobalPositionTarget(
			n.Latitude,
			n.Longitude,
			n.Altitude,
			n.Heading,
			options...,
		).Wait()
		if err != nil {
			return err
		}
		m.Log.Info().Msgf("waypoint %d reached!", i)
	}
	return nil
}

var _ dsl.Action = &Patrol{}
