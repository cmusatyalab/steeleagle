package actions

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
)

// Wait orders the vehicle to hold at its current position for Duration
// seconds.
type Wait struct {
	Duration float32 // seconds to wait
}

func (i *Wait) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	if _, err := v.Hold().Wait(); err != nil {
		return err
	}
	select {
	case <-time.After(time.Duration(float64(i.Duration) * float64(time.Second))):
		return nil
	case <-v.Ctx().Done():
		return nil
	}
}

var _ dsl.Action = &Wait{}
