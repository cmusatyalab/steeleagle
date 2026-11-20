package actions

// #begin-exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetVelocityTarget,steeleagle_protocol/v1/services/driver/ControlService/SetGimbalVelocityTarget,steeleagle_protocol/v1/services/driver/StreamService/StreamTelemetry,steeleagle_protocol/v1/messages/telemetry/GimbalInfo/pose_neu/pitch
import (
	"fmt"
	"math"
	"time"

	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// interval is the wait interval between loops.
const interval = 200 * time.Millisecond

// Track orders the vehicle to visually track an object in its field of view.
type Track struct {
	Camera params.Camera          // camera used for tracking (need FOV/resolution)
	Engine params.DetectionEngine // engine used for results
	Class  string                 // class to look for
	// #optional[3.0]
	LostDuration float32 // time in seconds before declaring target lost and exiting
	// #optional[-30.0]
	TargetPitch float32 // gimbal pitch in degrees to hold while tracking
	// #optional[180.0]
	YawSpeed float32 // yaw speed in degrees per second
	// #optional[20.0]
	PitchSpeed float32 // pitch speed in degrees per second
	// #optional[0.2]
	MoveOffsetMultiplier float32 // move speed in meters per second per degree of pitch from TargetPitch
	// #optional[3.0]
	MoveSpeed float32 // maximum move speed in meters per second
}

func (t *Track) Execute(v sdk.Vehicle, m dsl.MissionData) error {
	camera, err := m.Cap.GetCamera(string(t.Camera))
	if err != nil {
		m.Log.Error().Err(err).Str("camera", string(t.Camera)).Msg("couldn't find camera")
		return err
	}
	if camera.HFov == 0 || camera.VFov == 0 {
		return fmt.Errorf("camera %q has no field of view to track with", camera.Name)
	}
	if !camera.Gimbal {
		return fmt.Errorf("camera %q is not on the gimbal, so its pitch can't be used to track", camera.Name)
	}
	defer t.stop(v, m)

	lostAfter := time.Duration(float64(t.LostDuration) * float64(time.Second))
	lost := time.NewTimer(lostAfter)
	lost.Stop() // we only want to run the timer when no detections have been found
	defer lost.Stop()
	lostActive := false
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	lastQuery := time.Now() // so we only get new query results
	for {
		queried := time.Now()
		results, err := v.GetDetectionResult(t.Engine, opt.WithQueryStart[opt.QueryOption](lastQuery)).Wait()
		if err != nil {
			return err
		}
		lastQuery = queried

		var target sdk.BoundingBox
		if len(results) > 0 {
			// The newest result says whether the target is in view now
			target = t.findTarget(results[len(results)-1]) // oldest to newest
		}
		if target != nil {
			if lostActive { // reset the clock if we found something
				lost.Stop()
				lostActive = false
			}
			yaw, pitch := t.velocities(camera, target)
			x := t.moveVelocity(v, m)
			m.Log.Debug().Float32("yaw_vel", yaw).Float32("pitch_vel", pitch).Float32("x_vel", x).Msg("tracking target")
			if err := t.move(v, x, yaw, pitch); err != nil {
				return err
			}
		} else {
			// New results without the target mean it is out of view, so stop
			// rather than keep moving on old information; with no new results
			// the current motion is kept until the target is lost
			if len(results) > 0 {
				if err := t.move(v, 0, 0, 0); err != nil {
					return err
				}
			}
			if !lostActive { // wait to see if the target comes back
				lost.Reset(lostAfter)
				lostActive = true
			}
		}

		select {
		case <-v.Ctx().Done():
			return nil
		case <-lost.C:
			m.Log.Info().Str("class", t.Class).Msg("target lost")
			return nil
		case <-ticker.C: // pace polling to interval
		}
	}
}

// findTarget returns the bounding box of result's most confident detection
// of Class, or nil if it has none.
func (t *Track) findTarget(result sdk.DetectionResult) sdk.BoundingBox {
	var best sdk.BoundingBox
	bestScore := math.Inf(-1)
	for _, d := range result.GetDetections() {
		if d.GetClassName() != t.Class || d.GetScore() <= bestScore {
			continue
		}
		if bbox, err := d.GetBbox(); err == nil {
			best, bestScore = bbox, d.GetScore()
		}
	}
	return best
}

// velocities returns the yaw and gimbal pitch speeds that turn camera
// towards target.
func (t *Track) velocities(camera config.DriverCamera, target sdk.BoundingBox) (yaw, pitch float32) {
	// The target's center is offset to the right of the frame's center for
	// a positive yaw ratio, and below it for a negative pitch ratio, since
	// image y increases downwards
	yawRatio := angleRatio((target.GetXMin()+target.GetXMax())/2, camera.HFov)
	pitchRatio := -angleRatio((target.GetYMin()+target.GetYMax())/2, camera.VFov)
	yaw = float32(yawRatio) * t.YawSpeed
	pitch = float32(pitchRatio) * t.PitchSpeed
	return yaw, pitch
}

// moveVelocity returns the forward speed that brings the gimbal's pitch,
// which follows the target, back to TargetPitch, or 0 if the pitch is
// unknown. A pitch below TargetPitch (looking further down, e.g. -40 for
// -30) means the target is too close, so the vehicle moves backwards, and a
// pitch above it forwards, at MoveOffsetMultiplier m/s per degree off, up to
// MoveSpeed.
func (t *Track) moveVelocity(v sdk.Vehicle, m dsl.MissionData) float32 {
	current, err := gimbalPitch(v)
	if err != nil {
		m.Log.Debug().Err(err).Msg("no gimbal pitch, holding position")
		return 0
	}
	x := t.MoveOffsetMultiplier * (current - t.TargetPitch)
	return max(-t.MoveSpeed, min(t.MoveSpeed, x))
}

// gimbalPitch returns the gimbal's pitch in degrees from the vehicle's
// latest telemetry.
func gimbalPitch(v sdk.Vehicle) (float32, error) {
	telemetry, err := v.GetTelemetry().Wait()
	if err != nil {
		return 0, err
	}
	if len(telemetry) == 0 {
		return 0, fmt.Errorf("no telemetry received yet")
	}
	// Without a time range, only the most recent telemetry is returned
	gimbal, err := telemetry[len(telemetry)-1].GetGimbalInfo()
	if err != nil {
		return 0, err
	}
	pose, err := gimbal.GetPoseNeu()
	if err != nil {
		return 0, err
	}
	return pose.GetPitch()
}

// angleRatio returns the angle from the center of a camera's frame to center,
// a position across the frame from 0 to 1, as a ratio of half of the camera's
// fov in degrees, from -1 at the frame's start to 1 at its end.
func angleRatio(center float64, fov uint32) float64 {
	half := float64(fov) / 2 * math.Pi / 180
	offset := 2*center - 1 // -1 to 1 across the frame
	// For a pinhole camera, the frame spans tan(half) either side of its
	// center at unit distance
	return math.Atan(offset*math.Tan(half)) / half
}

// move sets the vehicle's forward and yaw velocities, and the gimbal's pitch
// velocity, returning the first command that fails.
func (t *Track) move(v sdk.Vehicle, x, yaw, pitch float32) error {
	// Without a reference frame, velocities are in the body frame, so x is
	// forwards
	if done, err := v.SetVelocityTarget(x, 0, 0, yaw).Check(); done && err != nil {
		return err
	}
	if done, err := v.SetGimbalVelocityTarget(pitch, 0, 0).Check(); done && err != nil {
		return err
	}
	return nil
}

// stop stops the vehicle and the gimbal once tracking is over.
func (t *Track) stop(v sdk.Vehicle, m dsl.MissionData) {
	if err := t.move(v, 0, 0, 0); err != nil {
		m.Log.Error().Err(err).Msg("couldn't stop after tracking")
	}
}

var _ dsl.Action = &Track{}

// #end-exclude
