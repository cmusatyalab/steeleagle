package actions

import (
	"github.com/cmusatyalab/steeleagle/dsl/types"
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// Patrol orders the vehicle to visit the waypoints in a RoutePlan.
type Patrol struct {
	types.RoutePlan
}

func (i *Patrol) Execute(v sdk.Vehicle) error {
	for {
		next, err := RoutePlan.GetNextWaypoint()
		if next == nil {
			return nil
		}
		_, err = v.SetGlobalPositionTarget(
			next.Latitude,
			next.Longitude,
			next.Altitude,
			next.Heading,
			next.Options...,
		).Wait()
		if err != nil {
			return nil
		}
	}
}

var _ dsl.Action = &Patrol{}
