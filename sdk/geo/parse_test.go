package geo

import (
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// TestAddFeaturesFromGeoJsonReturnsFeatureKeys checks that the returned
// feature slice matches the "name" property of each parsed feature, in
// order.
func TestAddFeaturesFromGeoJsonReturnsFeatureKeys(t *testing.T) {
	m := NewMap()
	features, err := m.AddFeaturesFromGeoJson([]byte(sampleGeoJSON))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []params.MapFeature{"area", "path"}
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
// retrieved from the map afterward via GetPolygon/GetLineString.
func TestAddFeaturesFromGeoJsonPopulatesMap(t *testing.T) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJson([]byte(sampleGeoJSON)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.GetPolygon("area"); err != nil {
		t.Errorf("GetPolygon(area): %v", err)
	}
	if _, err := m.GetLineString("path"); err != nil {
		t.Errorf("GetLineString(path): %v", err)
	}
}

// TestAddFeaturesFromGeoJsonAppendsToExisting checks that adding features
// to a map that already has geometry preserves the existing entries.
func TestAddFeaturesFromGeoJsonAppendsToExisting(t *testing.T) {
	m := testMap()
	if _, err := m.AddFeaturesFromGeoJson([]byte(sampleGeoJSON)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.GetPolygon("poly"); err != nil {
		t.Errorf("expected pre-existing feature %q to survive: %v", "poly", err)
	}
	if _, err := m.GetPolygon("area"); err != nil {
		t.Errorf("expected new feature %q to be added: %v", "area", err)
	}
}

// TestAddFeaturesFromGeoJsonInvalidJSON checks that malformed JSON surfaces
// an error instead of silently producing an empty map.
func TestAddFeaturesFromGeoJsonInvalidJSON(t *testing.T) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJson([]byte("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}

// TestGetFeatureNamesFromGeoJsonReturnsNames checks that the returned name
// slice matches the "name" property of each feature, in order.
func TestGetFeatureNamesFromGeoJsonReturnsNames(t *testing.T) {
	m := NewMap()
	names, err := m.GetFeatureNamesFromGeoJson([]byte(sampleGeoJSON))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"Area", "Path"}
	if len(names) != len(want) {
		t.Fatalf("expected %d names, got %d", len(want), len(names))
	}
	for i, n := range want {
		if names[i] != n {
			t.Errorf("name %d: got %q, want %q", i, names[i], n)
		}
	}
}

// TestGetFeatureNamesFromGeoJsonCapitalizesNames checks that every returned
// name has its first letter capitalized, regardless of the case it was
// stored in, and that an empty name is handled without panicking.
func TestGetFeatureNamesFromGeoJsonCapitalizesNames(t *testing.T) {
	const data = `{
		"type": "FeatureCollection",
		"features": [
			{"type":"Feature","properties":{"name":"lowercase"},"geometry":{"type":"Point","coordinates":[0,0]}},
			{"type":"Feature","properties":{"name":"AlreadyCapitalized"},"geometry":{"type":"Point","coordinates":[0,0]}},
			{"type":"Feature","properties":{"name":"ALLCAPS"},"geometry":{"type":"Point","coordinates":[0,0]}},
			{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[0,0]}}
		]
	}`
	m := NewMap()
	names, err := m.GetFeatureNamesFromGeoJson([]byte(data))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"Lowercase", "AlreadyCapitalized", "ALLCAPS", ""}
	if len(names) != len(want) {
		t.Fatalf("expected %d names, got %d", len(want), len(names))
	}
	for i, n := range want {
		if names[i] != n {
			t.Errorf("name %d: got %q, want %q", i, names[i], n)
		}
	}
}

// TestGetFeatureNamesFromGeoJsonDoesNotModifyMap checks that reading names
// out of GeoJSON data does not add any geometry to the map.
func TestGetFeatureNamesFromGeoJsonDoesNotModifyMap(t *testing.T) {
	m := testMap()
	if _, err := m.GetFeatureNamesFromGeoJson([]byte(sampleGeoJSON)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.GetPolygon("area"); err == nil {
		t.Error("expected GetFeatureNamesFromGeoJson not to add features to the map")
	}
	if _, err := m.GetPolygon("poly"); err != nil {
		t.Errorf("expected pre-existing feature %q to survive: %v", "poly", err)
	}
}

// TestGetFeatureNamesFromGeoJsonInvalidJSON checks that malformed JSON
// surfaces an error instead of silently producing an empty slice.
func TestGetFeatureNamesFromGeoJsonInvalidJSON(t *testing.T) {
	m := NewMap()
	if _, err := m.GetFeatureNamesFromGeoJson([]byte("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}
