package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
)

// GlobalPositionReached fires once the vehicle's global position is
// within tolerance of Target: Tolerance is a great-circle distance
// [meters] for latitude/longitude, AltitudeTolerance [meters] for
// altitude, and HeadingTolerance [degrees] for heading.
type GlobalPositionReached struct {
	Target types.GlobalPosition
	// #optional[0.5]
	Tolerance float32
	// #optional[0.5]
	AltitudeTolerance float32
	// #optional[3.0]
	HeadingTolerance float32
}

func (e *GlobalPositionReached) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
	ticker := time.NewTicker(tolerancePollInterval)
	defer ticker.Stop()
	for {
		select {
		case <-v.Ctx().Done():
			return false, nil
		case <-ticker.C:
			t, err := v.GetTelemetry().Wait()
			if err != nil {
				return false, err
			}
			pos, err := t.GetPositionInfo()
			if err != nil {
				continue // telemetry field not populated yet, keep polling
			}
			cur, err := pos.GetGlobalPosition()
			if err != nil {
				continue
			}

			lat, err := cur.GetLatitude()
			if err != nil {
				continue
			}
			lon, err := cur.GetLongitude()
			if err != nil {
				continue
			}
			alt, err := cur.GetAltitude()
			if err != nil {
				continue
			}
			heading, err := cur.GetHeading()
			if err != nil {
				continue
			}

			dist := haversineMeters(lat, lon, e.Target.Latitude, e.Target.Longitude)
			if dist <= float64(e.Tolerance) &&
				withinTolerance(alt, e.Target.Altitude, e.AltitudeTolerance) &&
				withinAngleTolerance(heading, e.Target.Heading, e.HeadingTolerance) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &GlobalPositionReached{}
