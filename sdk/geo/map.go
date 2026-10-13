package geo

import (
	"fmt"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/geom"
)

// Map holds GeoJSON data and can generate survey or corridor scans
// from the geometry.
type Map struct {
	geometry map[string]geom.Geometry // geometry map populated by GeoJSON/KML data
}

// NewMap builds an empty map.
func NewMap() *Map {
	return &Map{geometry: make(map[string]geom.Geometry)}
}

// NewMapFromGeoJson builds a Map from a GeoJSON FeatureCollection, keying
// each feature's geometry by its "name" property (see
// AddFeaturesFromGeoJson).
func NewMapFromGeoJson(data []byte) (*Map, error) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJson(data); err != nil {
		return nil, err
	}
	return m, nil
}

// Polygon gets a polygon from geometry by key and returns
// an error if it doesn't exist.
func (m *Map) Polygon(key params.Polygon) (geom.Polygon, error) {
	if val, ok := m.geometry[string(key)]; ok {
		ls, ok := val.AsPolygon()
		if !ok {
			return geom.Polygon{}, fmt.Errorf("key did not correspond to a polygon")
		} else {
			return ls, nil
		}
	} else {
		return geom.Polygon{}, fmt.Errorf("could not find key in geometry")
	}
}

// LineString gets a line string from geometry by key and returns
// an error if it doesn't exist.
func (m *Map) LineString(key params.LineString) (geom.LineString, error) {
	if val, ok := m.geometry[string(key)]; ok {
		ls, ok := val.AsLineString()
		if !ok {
			return geom.LineString{}, fmt.Errorf("key did not correspond to a line string")
		} else {
			return ls, nil
		}
	} else {
		return geom.LineString{}, fmt.Errorf("could not find key in geometry")
	}
}

// MultiLineString gets a multi line string from geometry by key and returns
// an error if it doesn't exist.
func (m *Map) MultiLineString(key params.MultiLineString) (geom.MultiLineString, error) {
	if val, ok := m.geometry[string(key)]; ok {
		ls, ok := val.AsMultiLineString()
		if !ok {
			return geom.MultiLineString{}, fmt.Errorf("key did not correspond to a multi line string")
		} else {
			return ls, nil
		}
	} else {
		return geom.MultiLineString{}, fmt.Errorf("could not find key in geometry")
	}
}

// Point gets a point from geometry by key and returns an error if it
// doesn't exist.
func (m *Map) Point(key params.Point) (geom.Point, error) {
	if val, ok := m.geometry[string(key)]; ok {
		ls, ok := val.AsPoint()
		if !ok {
			return geom.Point{}, fmt.Errorf("key did not correspond to a point")
		} else {
			return ls, nil
		}
	} else {
		return geom.Point{}, fmt.Errorf("could not find key in geometry")
	}
}
