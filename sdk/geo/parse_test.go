package geo

import (
	"strings"
	"testing"
)

// TestAddFeaturesFromGeoJsonReturnsFeatureKeys checks that the returned
// feature slice matches the "name" property of each parsed feature, in
// order.
func TestAddFeaturesFromGeoJsonReturnsFeatureKeys(t *testing.T) {
	m := NewMap()
	features, err := m.AddFeaturesFromGeoJson([]byte(sampleGeoJson))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"area", "path"}
	if len(features) != len(want) {
		t.Fatalf("expected %d features, got %d", len(want), len(features))
	}
	for i, f := range want {
		if features[i] != f {
			t.Errorf("feature %d: got %q, want %q", i, features[i], f)
		}
	}
}

// TestAddFeaturesFromGeoJsonPopulatesMap checks that parsed features can be
// retrieved from the map afterward via Polygon/LineString.
func TestAddFeaturesFromGeoJsonPopulatesMap(t *testing.T) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJson([]byte(sampleGeoJson)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.Polygon("area"); err != nil {
		t.Errorf("Polygon(area): %v", err)
	}
	if _, err := m.LineString("path"); err != nil {
		t.Errorf("LineString(path): %v", err)
	}
}

// TestAddFeaturesFromGeoJsonAppendsToExisting checks that adding features
// to a map that already has geometry preserves the existing entries.
func TestAddFeaturesFromGeoJsonAppendsToExisting(t *testing.T) {
	m := testMap()
	if _, err := m.AddFeaturesFromGeoJson([]byte(sampleGeoJson)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.Polygon("poly"); err != nil {
		t.Errorf("expected pre-existing feature %q to survive: %v", "poly", err)
	}
	if _, err := m.Polygon("area"); err != nil {
		t.Errorf("expected new feature %q to be added: %v", "area", err)
	}
}

// TestAddFeaturesFromGeoJsonInvalidJson checks that malformed JSON surfaces
// an error instead of silently producing an empty map.
func TestAddFeaturesFromGeoJsonInvalidJson(t *testing.T) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJson([]byte("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}

// TestFeatureNamesFromGeoJsonReturnsNames checks that the returned map
// groups each feature's "name" property under its geometry type.
func TestFeatureNamesFromGeoJsonReturnsNames(t *testing.T) {
	features, err := FeatureNamesFromGeoJson([]byte(sampleGeoJson))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	requireFeatureNames(t, features, map[string][]string{
		"Polygon":    {"area"},
		"LineString": {"path"},
	})
}

// TestFeatureNamesFromGeoJsonGroupsByType checks that features sharing a
// geometry type are all kept, in file order.
func TestFeatureNamesFromGeoJsonGroupsByType(t *testing.T) {
	const data = `{
		"type": "FeatureCollection",
		"features": [
			{"type":"Feature","properties":{"name":"a"},"geometry":{"type":"Point","coordinates":[0,0]}},
			{"type":"Feature","properties":{"name":"line"},"geometry":{"type":"LineString","coordinates":[[0,0],[1,1]]}},
			{"type":"Feature","properties":{"name":"b"},"geometry":{"type":"Point","coordinates":[1,1]}}
		]
	}`
	features, err := FeatureNamesFromGeoJson([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	requireFeatureNames(t, features, map[string][]string{
		"Point":      {"a", "b"},
		"LineString": {"line"},
	})
}

// TestFeatureNamesFromGeoJsonPreservesNames checks that every returned
// name is kept exactly as stored, without changing its case.
func TestFeatureNamesFromGeoJsonPreservesNames(t *testing.T) {
	const data = `{
		"type": "FeatureCollection",
		"features": [
			{"type":"Feature","properties":{"name":"lowercase"},"geometry":{"type":"Point","coordinates":[0,0]}},
			{"type":"Feature","properties":{"name":"AlreadyCapitalized"},"geometry":{"type":"Point","coordinates":[0,0]}},
			{"type":"Feature","properties":{"name":"ALLCAPS"},"geometry":{"type":"Point","coordinates":[0,0]}}
		]
	}`
	features, err := FeatureNamesFromGeoJson([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	requireFeatureNames(t, features, map[string][]string{
		"Point": {"lowercase", "AlreadyCapitalized", "ALLCAPS"},
	})
}

// requireFeatureNames checks that got holds exactly the types in want, each
// with the same names in the same order.
func requireFeatureNames(t *testing.T, got, want map[string][]string) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("expected %d types, got %d: %v", len(want), len(got), got)
	}
	for typ, names := range want {
		gotNames, ok := got[typ]
		if !ok {
			t.Errorf("missing type %q", typ)
			continue
		}
		if len(gotNames) != len(names) {
			t.Errorf("type %q: got %v, want %v", typ, gotNames, names)
			continue
		}
		for i, n := range names {
			if gotNames[i] != n {
				t.Errorf("type %q name %d: got %q, want %q", typ, i, gotNames[i], n)
			}
		}
	}
}

// TestFeatureNamesFromGeoJsonInvalidJson checks that malformed JSON
// surfaces an error instead of silently producing an empty slice.
func TestFeatureNamesFromGeoJsonInvalidJson(t *testing.T) {
	if _, err := FeatureNamesFromGeoJson([]byte("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}

// invalidFeatures are GeoJSON FeatureCollections with a feature that both
// FeatureNamesFromGeoJson and AddFeaturesFromGeoJson reject, by the error
// they must report.
var invalidFeatures = map[string]string{
	"feature 1 has no name property": `{"type":"FeatureCollection","features":[
		{"type":"Feature","properties":{"name":"a"},"geometry":{"type":"Point","coordinates":[0,0]}},
		{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[0,0]}}]}`,
	"feature 0 has no name property": `{"type":"FeatureCollection","features":[
		{"type":"Feature","properties":{"name":7},"geometry":{"type":"Point","coordinates":[0,0]}}]}`,
	`name "a" is used more than once`: `{"type":"FeatureCollection","features":[
		{"type":"Feature","properties":{"name":"a"},"geometry":{"type":"Point","coordinates":[0,0]}},
		{"type":"Feature","properties":{"name":"a"},"geometry":{"type":"LineString","coordinates":[[0,0],[1,1]]}}]}`,
	`feature "m" is a MultiPolygon`: `{"type":"FeatureCollection","features":[
		{"type":"Feature","properties":{"name":"m"},"geometry":{"type":"MultiPolygon","coordinates":[]}}]}`,
}

// TestFeatureNamesFromGeoJsonRejectsInvalidFeatures checks that unnamed,
// duplicate and unsupported features are reported.
func TestFeatureNamesFromGeoJsonRejectsInvalidFeatures(t *testing.T) {
	for want, data := range invalidFeatures {
		_, err := FeatureNamesFromGeoJson([]byte(data))
		if err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("FeatureNamesFromGeoJson() error = %v, want one containing %q", err, want)
		}
	}
}

// TestAddFeaturesFromGeoJsonRejectsInvalidFeatures checks that invalid
// features are reported rather than panicking, and that nothing is added
// to the map when any feature is invalid.
func TestAddFeaturesFromGeoJsonRejectsInvalidFeatures(t *testing.T) {
	for want, data := range invalidFeatures {
		m := NewMap()
		_, err := m.AddFeaturesFromGeoJson([]byte(data))
		if err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("AddFeaturesFromGeoJson() error = %v, want one containing %q", err, want)
		}
		if len(m.geometry) != 0 {
			t.Errorf("AddFeaturesFromGeoJson() added %d features despite the error", len(m.geometry))
		}
	}
}

// TestAddFeaturesFromGeoJsonRejectsNameInMap checks that a feature can't
// replace one already in the map.
func TestAddFeaturesFromGeoJsonRejectsNameInMap(t *testing.T) {
	m := testMap()
	data := `{"type":"FeatureCollection","features":[
		{"type":"Feature","properties":{"name":"poly"},"geometry":{"type":"Point","coordinates":[0,0]}}]}`
	if _, err := m.AddFeaturesFromGeoJson([]byte(data)); err == nil || !strings.Contains(err.Error(), "already in the map") {
		t.Errorf("AddFeaturesFromGeoJson() error = %v, want one about poly already being in the map", err)
	}
	if _, err := m.Polygon("poly"); err != nil {
		t.Errorf("existing feature poly was replaced: %v", err)
	}
}
