// Package events holds every dsl.Event implementation a mission can
// trigger a transition on -- one file per event, discovered automatically
// by the compiler's registry loader (see sdk/dsl/loader) from any exported
// struct that implements dsl.Event.
package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// BatteryLow fires once the vehicle's battery percentage drops to or below
// Threshold.
type BatteryLow struct {
	// #optional[20]
	Threshold uint32 // battery percentage
}

func (e *BatteryLow) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
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
			batt, err := t.GetBatteryInfo()
			if err != nil {
				continue // telemetry field not populated yet, keep polling
			}
			pct, err := batt.GetPercentage()
			if err != nil {
				continue
			}
			if pct <= e.Threshold {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &BatteryLow{}
