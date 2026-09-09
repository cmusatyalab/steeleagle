package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
)

// velocity is satisfied by both PositionInfo_VelocityBody and
// PositionInfo_VelocityNeu, letting Monitor read either through one path.
type velocity interface {
	GetXVel() (float32, error)
	GetYVel() (float32, error)
	GetZVel() (float32, error)
	GetAngularVel() (float32, error)
}

// VelocityReached fires once the vehicle's velocity is within Tolerance
// of Target on every axis. Frame selects which telemetry velocity to
// compare against.
type VelocityReached struct {
	Target types.Velocity
	// #optional[0]
	Tolerance float32
	Frame     enums.ReferenceFrame
}

func (e *VelocityReached) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
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

			var vel velocity
			if e.Frame == enums.ReferenceFrameNeu {
				vel, err = pos.GetVelocityNeu()
			} else {
				vel, err = pos.GetVelocityBody()
			}
			if err != nil {
				continue
			}

			xVel, err := vel.GetXVel()
			if err != nil {
				continue
			}
			yVel, err := vel.GetYVel()
			if err != nil {
				continue
			}
			zVel, err := vel.GetZVel()
			if err != nil {
				continue
			}
			angularVel, err := vel.GetAngularVel()
			if err != nil {
				continue
			}

			if withinTolerance(xVel, e.Target.XVel, e.Tolerance) &&
				withinTolerance(yVel, e.Target.YVel, e.Tolerance) &&
				withinTolerance(zVel, e.Target.ZVel, e.Tolerance) &&
				withinTolerance(angularVel, e.Target.AngularVel, e.Tolerance) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &VelocityReached{}
