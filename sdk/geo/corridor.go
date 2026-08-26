package geo

import (
	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// CorridorScan lists out the vertices of a lon/lat polygon as GlobalPosition
// types for point-by-point traversal.
func (m *Map) CorridorScan(area params.MapFeature, altitude float32) ([]GeoPoint, error) {
	// Retrieve polygon from store
	poly, err := m.GetPolygon(area)
	if err != nil {
		return nil, err
	}

	// Extract points
	coords := poly.ExteriorRing().Coordinates()
	points := make([]GeoPoint, coords.Length())
	for i := 0; i < coords.Length(); i++ {
		xy := coords.GetXY(i)
		points[i] = GeoPoint{
			Longitude: xy.X,
			Latitude:  xy.Y,
			Altitude:  altitude,
		}
		if i >= 1 { // set heading if it isn't the first point
			hdg := Bearing(points[i-1], points[i])
			points[i].Heading = hdg
		}
	}
	return points, nil
}
