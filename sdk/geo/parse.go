package geo

import (
	"encoding/json"
	"fmt"

	"github.com/peterstace/simplefeatures/geom"
)

// featureTypes are the GeoJSON geometry types a Map can look features up
// as (see Map.Point, Map.LineString, Map.MultiLineString and Map.Polygon),
// each of which the params package declares a feature type for.
var featureTypes = map[geom.GeometryType]bool{
	geom.TypePoint:           true,
	geom.TypeLineString:      true,
	geom.TypeMultiLineString: true,
	geom.TypePolygon:         true,
}

// feature is a named feature of a GeoJSON FeatureCollection.
type feature struct {
	name     string
	geometry geom.Geometry
}

// parseFeatures decodes a GeoJSON FeatureCollection, in file order. Every
// feature must have a non-empty string "name" property that no other
// feature has, and a geometry of one of featureTypes.
func parseFeatures(data []byte) ([]feature, error) {
	var fc geom.GeoJSONFeatureCollection
	if err := json.Unmarshal(data, &fc); err != nil {
		return nil, err
	}
	features := make([]feature, 0, len(fc.Features))
	seen := make(map[string]bool, len(fc.Features))
	for i, f := range fc.Features {
		name, _ := f.Properties["name"].(string)
		if name == "" {
			return nil, fmt.Errorf("GeoJSON feature %d has no name property", i)
		}
		if seen[name] {
			return nil, fmt.Errorf("GeoJSON feature name %q is used more than once", name)
		}
		seen[name] = true
		if typ := f.Geometry.Type(); !featureTypes[typ] {
			return nil, fmt.Errorf(
				"GeoJSON feature %q is a %s, but only Point, LineString, MultiLineString and Polygon features are supported",
				name, typ,
			)
		}
		features = append(features, feature{name: name, geometry: f.Geometry})
	}
	return features, nil
}

// AddFeaturesFromGeoJson parses the features of a GeoJSON
// FeatureCollection into the map, keyed by their "name" property, and
// returns their names in file order. Every feature must be named, with a
// name not already in the map, and be a Point, LineString,
// MultiLineString or Polygon. Nothing is added if any feature is invalid.
func (m *Map) AddFeaturesFromGeoJson(data []byte) ([]string, error) {
	features, err := parseFeatures(data)
	if err != nil {
		return nil, err
	}
	if m.geometry == nil {
		m.geometry = make(map[string]geom.Geometry, len(features))
	}
	names := make([]string, 0, len(features))
	for _, f := range features {
		if _, ok := m.geometry[f.name]; ok {
			return nil, fmt.Errorf("GeoJSON feature name %q is already in the map", f.name)
		}
		names = append(names, f.name)
	}
	for _, f := range features {
		m.geometry[f.name] = f.geometry
	}
	return names, nil
}

// FeatureNamesFromGeoJson parses the features of a GeoJSON
// FeatureCollection, validated as for AddFeaturesFromGeoJson, and returns
// a map from geometry type to the names of all features of that type, in
// file order.
func FeatureNamesFromGeoJson(data []byte) (map[string][]string, error) {
	features, err := parseFeatures(data)
	if err != nil {
		return nil, err
	}
	names := make(map[string][]string)
	for _, f := range features {
		typ := f.geometry.Type().String()
		names[typ] = append(names[typ], f.name)
	}
	return names, nil
}
