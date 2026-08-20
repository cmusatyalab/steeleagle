package geo

import (
	"github.com/peterstace/simplefeatures/geom"
)

// testMap creates a mock map for testing.
func testMap() *Map {
	poly := geom.NewSingleRingPolygonXY(0, 0, 0, 10, 10, 10, 10, 0, 0, 0)
	line := geom.NewLineStringXY(0, 0, 10, 10)
	return &Map{
		placemarks: map[string]geom.Geometry{
			"poly": poly.AsGeometry(),
			"line": line.AsGeometry(),
		},
	}
}
