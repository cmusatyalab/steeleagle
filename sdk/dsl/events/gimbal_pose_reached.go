package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
)

// gimbalPose is satisfied by both GimbalInfo_PoseBody and
// GimbalInfo_PoseNeu, letting Monitor read either through one path.
type gimbalPose interface {
	GetPitch() (float32, error)
	GetRoll() (float32, error)
	GetYaw() (float32, error)
}

// GimbalPoseReached fires once the vehicle's primary gimbal pose is
// within Tolerance of Target on every axis. Frame selects which
// telemetry pose to compare against.
type GimbalPoseReached struct {
	Target types.Pose
	// #optional[3.0]
	Tolerance float32
	Frame     enums.ReferenceFrame
}

func (e *GimbalPoseReached) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
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
			gimbal, err := t.GetGimbalInfo()
			if err != nil {
				continue // telemetry field not populated yet, keep polling
			}

			var pose gimbalPose
			if e.Frame == enums.ReferenceFrameNeu {
				pose, err = gimbal.GetPoseNeu()
			} else {
				pose, err = gimbal.GetPoseBody()
			}
			if err != nil {
				continue
			}

			pitch, err := pose.GetPitch()
			if err != nil {
				continue
			}
			roll, err := pose.GetRoll()
			if err != nil {
				continue
			}
			yaw, err := pose.GetYaw()
			if err != nil {
				continue
			}

			if withinTolerance(pitch, e.Target.Pitch, e.Tolerance) &&
				withinTolerance(roll, e.Target.Roll, e.Tolerance) &&
				withinTolerance(yaw, e.Target.Yaw, e.Tolerance) {
				return true, nil
			}
		}
	}
}

var _ dsl.Event = &GimbalPoseReached{}
