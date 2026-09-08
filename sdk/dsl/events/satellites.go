package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// Satellites fires once the vehicle's GPS satellite count satisfies
// Comparator against Threshold (e.g. GreaterOrEqual to detect a GPS lock).
type Satellites struct {
	// #optional[6]
	Threshold  uint32 // GPS satellite count
	Comparator Comparator
}

func (e *Satellites) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
	ticker := time.NewTicker(1 * time.Second)
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
			gps, err := t.GetGpsInfo()
			if err != nil {
				continue // telemetry field not populated yet, keep polling
			}
			sats, err := gps.GetSatellites()
			if err != nil {
				continue
			}
			if compareUint32(sats, e.Threshold, e.Comparator) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &Satellites{}
