package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
)

// RelativePositionReached fires once the vehicle's relative position is
// within tolerance of Target on every axis: Tolerance for X/Y/Z
// [meters], AngleTolerance for Angle [degrees].
type RelativePositionReached struct {
	Target types.RelativePosition
	// #optional[0.20]
	Tolerance float32
	// #optional[0]
	AngleTolerance float32
}

func (e *RelativePositionReached) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
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
			rel, err := pos.GetRelativePosition()
			if err != nil {
				continue
			}

			x, err := rel.GetX()
			if err != nil {
				continue
			}
			y, err := rel.GetY()
			if err != nil {
				continue
			}
			z, err := rel.GetZ()
			if err != nil {
				continue
			}
			angle, err := rel.GetAngle()
			if err != nil {
				continue
			}

			if withinTolerance(x, e.Target.X, e.Tolerance) &&
				withinTolerance(y, e.Target.Y, e.Tolerance) &&
				withinTolerance(z, e.Target.Z, e.Tolerance) &&
				withinAngleTolerance(angle, e.Target.Angle, e.AngleTolerance) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &RelativePositionReached{}
