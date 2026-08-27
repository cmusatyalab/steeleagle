package geo

import (
	"encoding/json"
	"unicode"
	"unicode/utf8"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/geom"
)

// AddFeaturesFromGeoJson reads in a byte slice of GeoJSON data and parses out
// geometry objects from it into the map object.
func (m *Map) AddFeaturesFromGeoJson(data []byte) ([]params.MapFeature, error) {
	var fc geom.GeoJSONFeatureCollection
	if err := json.Unmarshal(data, &fc); err != nil {
		return nil, err
	}
	if m.geometry == nil {
		m.geometry = make(map[params.MapFeature]geom.Geometry, len(fc.Features))
	}
	features := make([]params.MapFeature, 0, len(fc.Features))
	for _, f := range fc.Features {
		name, _ := f.Properties["name"].(string)
		fname := params.MapFeature(name) // get a wrapped feature name
		m.geometry[fname] = f.Geometry
		features = append(features, fname)
	}

	return features, nil
}

// GetFeatureNamesFromGeoJson reads in a byte slice of GeoJSON data and parses
// out the names of all features inside it, without modifying the map.
func (m *Map) GetFeatureNamesFromGeoJson(data []byte) ([]string, error) {
	var fc geom.GeoJSONFeatureCollection
	if err := json.Unmarshal(data, &fc); err != nil {
		return nil, err
	}
	names := make([]string, 0, len(fc.Features))
	for _, f := range fc.Features {
		name, _ := f.Properties["name"].(string)
		names = append(names, capitalize(name))
	}

	return names, nil
}

// capitalize uppercases the first rune of s, leaving the rest unchanged.
func capitalize(s string) string {
	if s == "" {
		return s
	}
	r, size := utf8.DecodeRuneInString(s)
	return string(unicode.ToUpper(r)) + s[size:]
}
