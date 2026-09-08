package events

import "time"

// tolerancePollInterval paces every tolerance-based event's telemetry poll.
// Position/altitude/velocity/gimbal-pose telemetry changes far more
// granularly than e.g. battery percentage or satellite count, so these
// events poll at 10Hz rather than the once-a-second rate those use.
const tolerancePollInterval = 100 * time.Millisecond

// withinTolerance reports whether cur is within tol of target.
func withinTolerance(cur, target, tol float32) bool {
	diff := cur - target
	if diff < 0 {
		diff = -diff
	}
	return diff <= tol
}
