package events

import (
	"math"
	"time"
)

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

// withinAngleTolerance reports whether cur is within tol degrees of
// target, accounting for wraparound (e.g. 359 and 1 are 2 degrees apart,
// not 358).
func withinAngleTolerance(cur, target, tol float32) bool {
	diff := math.Mod(float64(cur-target), 360)
	if diff < 0 {
		diff += 360
	}
	if diff > 180 {
		diff = 360 - diff
	}
	return float32(diff) <= tol
}

// earthRadiusMeters is the mean Earth radius used by haversineMeters.
const earthRadiusMeters = 6371000.0

// haversineMeters returns the great-circle distance, in meters, between
// two latitude/longitude points given in degrees.
func haversineMeters(lat1, lon1, lat2, lon2 float64) float64 {
	lat1r, lon1r := lat1*math.Pi/180, lon1*math.Pi/180
	lat2r, lon2r := lat2*math.Pi/180, lon2*math.Pi/180
	dlat, dlon := lat2r-lat1r, lon2r-lon1r
	h := math.Sin(dlat/2)*math.Sin(dlat/2) +
		math.Cos(lat1r)*math.Cos(lat2r)*math.Sin(dlon/2)*math.Sin(dlon/2)
	return 2 * earthRadiusMeters * math.Asin(math.Sqrt(h))
}
