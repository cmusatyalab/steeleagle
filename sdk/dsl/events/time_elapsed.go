package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// TimeElapsed fires once Duration seconds have passed since the state
// hosting this event was entered.
type TimeElapsed struct {
	Duration float32 // seconds to wait before firing
}

func (e *TimeElapsed) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
	select {
	case <-time.After(time.Duration(float64(e.Duration) * float64(time.Second))):
		return true, nil
	case <-v.Ctx().Done():
		return false, nil
	}
}

var _ dsl.Event = &TimeElapsed{}
