package geo

import (
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// TestAddFeaturesFromGeoJSONReturnsFeatureKeys checks that the returned
// feature slice matches the "name" property of each parsed feature, in
// order.
func TestAddFeaturesFromGeoJSONReturnsFeatureKeys(t *testing.T) {
	m := NewMap()
	features, err := m.AddFeaturesFromGeoJSON([]byte(sampleGeoJSON))
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

// TestAddFeaturesFromGeoJSONPopulatesMap checks that parsed features can be
// retrieved from the map afterward via GetPolygon/GetLineString.
func TestAddFeaturesFromGeoJSONPopulatesMap(t *testing.T) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJSON([]byte(sampleGeoJSON)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.GetPolygon("area"); err != nil {
		t.Errorf("GetPolygon(area): %v", err)
	}
	if _, err := m.GetLineString("path"); err != nil {
		t.Errorf("GetLineString(path): %v", err)
	}
}

// TestAddFeaturesFromGeoJSONAppendsToExisting checks that adding features
// to a map that already has geometry preserves the existing entries.
func TestAddFeaturesFromGeoJSONAppendsToExisting(t *testing.T) {
	m := testMap()
	if _, err := m.AddFeaturesFromGeoJSON([]byte(sampleGeoJSON)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.GetPolygon("poly"); err != nil {
		t.Errorf("expected pre-existing feature %q to survive: %v", "poly", err)
	}
	if _, err := m.GetPolygon("area"); err != nil {
		t.Errorf("expected new feature %q to be added: %v", "area", err)
	}
}

// TestAddFeaturesFromGeoJSONInvalidJSON checks that malformed JSON surfaces
// an error instead of silently producing an empty map.
func TestAddFeaturesFromGeoJSONInvalidJSON(t *testing.T) {
	m := NewMap()
	if _, err := m.AddFeaturesFromGeoJSON([]byte("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}
