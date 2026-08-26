package geo

import (
	"fmt"
	"io"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/geom"
)

// Map holds GeoJSON data and can generate survey or corridor scans
// from the geometry.
type Map struct {
	geometry map[params.MapFeature]geom.Geometry // geometry map populated by GeoJSON/KML data
}

// NewMap builds an empty map.
func NewMap() *Map {
	return &Map{geometry: make(map[params.MapFeature]geom.Geometry)}
}

// NewMapFromGeoJSON builds a Map from a GeoJSON FeatureCollection, keying
// each feature's geometry by its "name" property.
func NewMapFromGeoJSON(r io.Reader) (*Map, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJSON(data); err != nil {
		return nil, err
	}
	return m, nil
}

// GetPolygon gets a polygon from geometry by key and returns
// an error if it doesn't exist.
func (m *Map) GetPolygon(key params.MapFeature) (geom.Polygon, error) {
	if val, ok := m.geometry[key]; ok {
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

// GetLineString gets a line string from geometry by key and returns
// an error if it doesn't exist.
func (m *Map) GetLineString(key params.MapFeature) (geom.LineString, error) {
	if val, ok := m.geometry[key]; ok {
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
