package actions

// #begin-exclude-ifndef steeleagle_protocol/v1/services/driver/ControlService/SetVelocityTarget,steeleagle_protocol/v1/services/driver/ControlService/SetGimbalVelocityTarget
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
	// #optional[0.2]
	TargetAreaRatio float32 // target bounding box ratio of the camera frame size
	// #optional[120.0]
	YawSpeed float32 // yaw speed in degrees per second
	// #optional[90.0]
	PitchSpeed float32 // pitch speed in degrees per second
	// #optional[3.0]
	MoveSpeed float32 // move speed in meters per second
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
	if t.TargetAreaRatio <= 0 {
		return fmt.Errorf("target area ratio %v must be positive", t.TargetAreaRatio)
	}
	if !camera.Gimbal {
		m.Log.Warn().Str("camera", camera.Name).Msg("camera is not on the gimbal, so the target is not tracked in pitch")
	}
	defer t.stop(v, m, camera)

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
			yaw, pitch, x := t.velocities(camera, target)
			m.Log.Debug().Float32("yaw_vel", yaw).Float32("pitch_vel", pitch).Float32("x_vel", x).Msg("tracking target")
			if err := t.move(v, camera, x, yaw, pitch); err != nil {
				return err
			}
		} else {
			// New results without the target mean it is out of view, so stop
			// rather than keep moving on old information; with no new results
			// the current motion is kept until the target is lost
			if len(results) > 0 {
				if err := t.move(v, camera, 0, 0, 0); err != nil {
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
// towards target, and the forward speed that brings target to
// TargetAreaRatio of the frame.
func (t *Track) velocities(camera config.DriverCamera, target sdk.BoundingBox) (yaw, pitch, x float32) {
	// The target's center is offset to the right of the frame's center for
	// a positive yaw ratio, and below it for a negative pitch ratio, since
	// image y increases downwards
	yawRatio := angleRatio((target.GetXMin()+target.GetXMax())/2, camera.HFov)
	pitchRatio := -angleRatio((target.GetYMin()+target.GetYMax())/2, camera.VFov)
	yaw = float32(yawRatio) * t.YawSpeed
	pitch = float32(pitchRatio) * t.PitchSpeed

	// Bounding boxes are fractions of the frame, so their area is already
	// their ratio of the frame's area. A target larger than wanted (e.g. 1.3x,
	// a difference of 0.3) moves the vehicle away, and a smaller one (e.g.
	// 0.7x, -0.3) towards it, at up to MoveSpeed
	area := (target.GetXMax() - target.GetXMin()) * (target.GetYMax() - target.GetYMin())
	difference := float32(area)/t.TargetAreaRatio - 1
	x = max(-t.MoveSpeed, min(t.MoveSpeed, -difference*t.MoveSpeed))
	return yaw, pitch, x
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
// velocity if camera is on it, returning the first command that fails.
func (t *Track) move(v sdk.Vehicle, camera config.DriverCamera, x, yaw, pitch float32) error {
	// Without a reference frame, velocities are in the body frame, so x is
	// forwards
	if done, err := v.SetVelocityTarget(x, 0, 0, yaw).Check(); done && err != nil {
		return err
	}
	if camera.Gimbal {
		if done, err := v.SetGimbalVelocityTarget(pitch, 0, 0).Check(); done && err != nil {
			return err
		}
	}
	return nil
}

// stop stops the vehicle and the gimbal once tracking is over.
func (t *Track) stop(v sdk.Vehicle, m dsl.MissionData, camera config.DriverCamera) {
	if err := t.move(v, camera, 0, 0, 0); err != nil {
		m.Log.Error().Err(err).Msg("couldn't stop after tracking")
	}
}

var _ dsl.Action = &Track{}

// #end-exclude
