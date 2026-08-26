package geo

import (
	"encoding/json"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/geom"
)

// AddFeaturesFromGeoJSON reads in a byte slice of GeoJSON data and parses out
// geometry objects from it into the map object.
func (m *Map) AddFeaturesFromGeoJSON(data []byte) ([]params.MapFeature, error) {
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
