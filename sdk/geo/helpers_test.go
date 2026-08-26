package geo

import (
	"math"
	"testing"

	"github.com/peterstace/simplefeatures/geom"
)

// sampleGeoJSON is a small FeatureCollection with one polygon and one line
// string feature, used across parse and map tests.
const sampleGeoJSON = `{
	"type": "FeatureCollection",
	"features": [
		{"type":"Feature","properties":{"name":"area"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[0,10],[10,10],[10,0],[0,0]]]}},
		{"type":"Feature","properties":{"name":"path"},"geometry":{"type":"LineString","coordinates":[[0,0],[10,10]]}}
	]
}`

// requireXY checks whether want is within tol of got.
func requireXY(t *testing.T, got, want geom.XY, tol float64, label string) {
	t.Helper()
	if math.Abs(got.X-want.X) > tol || math.Abs(got.Y-want.Y) > tol {
		t.Errorf("%s: got (%.6f,%.6f), want (%.6f,%.6f) (tol %v)", label, got.X, got.Y, want.X, want.Y, tol)
	}
}
