package geo

import (
	"math"
	"testing"
)

// TestDistanceMeters checks DistanceMeters against known distances.
func TestDistanceMeters(t *testing.T) {
	tests := []struct {
		lat1, lon1, lat2, lon2, want float64
	}{
		{0, 0, 0, 0, 0},
		{0, 0, 0, 1, 111195}, // one degree of longitude at the equator
		{0, 0, 1, 0, 111195}, // one degree of latitude
	}
	for _, tt := range tests {
		got := DistanceMeters(tt.lat1, tt.lon1, tt.lat2, tt.lon2)
		if math.Abs(got-tt.want) > 0.001*tt.want+1 {
			t.Errorf("DistanceMeters(%v, %v, %v, %v) = %.0f, want %.0f", tt.lat1, tt.lon1, tt.lat2, tt.lon2, got, tt.want)
		}
	}
}

// TestAngleDiff checks that AngleDiff takes the short way around, for
// angles in any range.
func TestAngleDiff(t *testing.T) {
	tests := []struct{ a, b, want float32 }{
		{10, 20, 10},
		{20, 10, 10},
		{359, 1, 2},
		{1, 359, 2},
		{0, 180, 180},
		{-170, 170, 20},
		{720, 1, 1},
	}
	for _, tt := range tests {
		if got := AngleDiff(tt.a, tt.b); math.Abs(float64(got-tt.want)) > 1e-4 {
			t.Errorf("AngleDiff(%v, %v) = %v, want %v", tt.a, tt.b, got, tt.want)
		}
	}
}
