package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
)

// AltitudeReached fires once the vehicle's altitude is within Tolerance of
// Altitude. AltitudeMode selects which telemetry altitude to compare
// against: AltitudeModeAbsolute reads global (MSL) altitude,
// AltitudeModeRelative reads altitude relative to takeoff.
type AltitudeReached struct {
	Altitude float32
	// #optional[0.5]
	Tolerance    float32
	AltitudeMode enums.AltitudeMode
}

func (e *AltitudeReached) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
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

			var cur float32
			if e.AltitudeMode == enums.AltitudeModeAbsolute {
				gp, err := pos.GetGlobalPosition()
				if err != nil {
					continue
				}
				cur, err = gp.GetAltitude()
				if err != nil {
					continue
				}
			} else {
				rp, err := pos.GetRelativePosition()
				if err != nil {
					continue
				}
				cur, err = rp.GetZ()
				if err != nil {
					continue
				}
			}

			if withinTolerance(cur, e.Altitude, e.Tolerance) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &AltitudeReached{}
