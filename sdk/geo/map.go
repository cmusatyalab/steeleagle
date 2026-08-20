package geo

import (
	"fmt"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
	"github.com/peterstace/simplefeatures/geom"
)

// Map holds GeoJSON data and can generate survey or corridor scans
// from the geometry.
type Map struct {
	centroid   types.GlobalPosition     // the map center, used to get UTM projector
	placemarks map[string]geom.Geometry // placemark map populated by GeoJSON data
}

// GetPolygon gets a polygon from placemarks by key and returns
// an error if it doesn't exist.
func (m *Map) GetPolygon(key string) (geom.Polygon, error) {
	if val, ok := m.placemarks[key]; ok {
		ls, ok := val.AsPolygon()
		if !ok {
			return geom.Polygon{}, fmt.Errorf("key did not correspond to a polygon")
		} else {
			return ls, nil
		}
	} else {
		return geom.Polygon{}, fmt.Errorf("could not find key in placemarks")
	}
}

// GetLineString gets a line string from placemarks by key and returns
// an error if it doesn't exist.
func (m *Map) GetLineString(key string) (geom.LineString, error) {
	if val, ok := m.placemarks[key]; ok {
		ls, ok := val.AsLineString()
		if !ok {
			return geom.LineString{}, fmt.Errorf("key did not correspond to a line string")
		} else {
			return ls, nil
		}
	} else {
		return geom.LineString{}, fmt.Errorf("could not find key in placemarks")
	}
}
