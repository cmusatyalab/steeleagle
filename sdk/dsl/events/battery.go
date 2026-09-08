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

// Battery fires once the vehicle's battery percentage satisfies Comparator
// against Threshold (e.g. LessOrEqual for a low-battery warning,
// GreaterOrEqual to detect a full charge).
type Battery struct {
	// #optional[20]
	Threshold  uint32 // battery percentage
	Comparator Comparator
}

func (e *Battery) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
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
			if compareUint32(pct, e.Threshold, e.Comparator) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &Battery{}
