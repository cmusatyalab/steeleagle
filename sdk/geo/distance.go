package geo

import "math"

// earthRadiusMeters is the mean Earth radius used by DistanceMeters.
const earthRadiusMeters = 6371000.0

// DistanceMeters returns the great-circle (haversine) distance in meters
// between two latitude/longitude points given in degrees.
func DistanceMeters(lat1, lon1, lat2, lon2 float64) float64 {
	toRad := func(deg float64) float64 { return deg * math.Pi / 180 }
	dLat := toRad(lat2 - lat1)
	dLon := toRad(lon2 - lon1)
	h := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(toRad(lat1))*math.Cos(toRad(lat2))*math.Sin(dLon/2)*math.Sin(dLon/2)
	return 2 * earthRadiusMeters * math.Asin(math.Sqrt(h))
}

// AngleDiff returns the smallest difference in degrees between two angles
// in degrees, accounting for wraparound (e.g. 359 and 1 are 2 degrees
// apart, not 358), whatever range the angles are given in.
func AngleDiff(a, b float32) float32 {
	d := math.Mod(float64(a-b), 360)
	if d < 0 {
		d += 360
	}
	if d > 180 {
		d = 360 - d
	}
	return float32(d)
}
