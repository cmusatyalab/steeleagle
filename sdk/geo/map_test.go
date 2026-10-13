package geo

import (
	"testing"
)

// TestPolygonFound checks that Polygon returns the polygon stored
// under a matching key.
func TestPolygonFound(t *testing.T) {
	m := testMap()
	poly, err := m.Polygon("poly")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if poly.AsGeometry().IsEmpty() {
		t.Error("expected a non-empty polygon")
	}
}

// TestPolygonMissingKey checks that Polygon errors when the key
// isn't present in geometry.
func TestPolygonMissingKey(t *testing.T) {
	m := testMap()
	if _, err := m.Polygon("missing"); err == nil {
		t.Fatal("expected an error for a missing key")
	}
}

// TestPolygonWrongType checks that Polygon errors when the key maps
// to a geometry that isn't a polygon.
func TestPolygonWrongType(t *testing.T) {
	m := testMap()
	if _, err := m.Polygon("line"); err == nil {
		t.Fatal("expected an error for a key that isn't a polygon")
	}
}

// TestLineStringFound checks that LineString returns the line
// string stored under a matching key.
func TestLineStringFound(t *testing.T) {
	m := testMap()
	ls, err := m.LineString("line")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ls.AsGeometry().IsEmpty() {
		t.Error("expected a non-empty line string")
	}
}

// TestLineStringMissingKey checks that LineString errors when the
// key isn't present in geometry.
func TestLineStringMissingKey(t *testing.T) {
	m := testMap()
	if _, err := m.LineString("missing"); err == nil {
		t.Fatal("expected an error for a missing key")
	}
}

// TestLineStringWrongType checks that LineString errors when the
// key maps to a geometry that isn't a line string.
func TestLineStringWrongType(t *testing.T) {
	m := testMap()
	if _, err := m.LineString("poly"); err == nil {
		t.Fatal("expected an error for a key that isn't a line string")
	}
}

// TestNewMapIsEmpty checks that NewMap returns a usable map with no
// geometry in it.
func TestNewMapIsEmpty(t *testing.T) {
	m := NewMap()
	if _, err := m.Polygon("anything"); err == nil {
		t.Fatal("expected an error looking up a polygon in an empty map")
	}
}

// TestNewMapFromGeoJsonBuildsUsableMap checks that a map built directly
// from GeoJSON data can be queried via Polygon/LineString.
func TestNewMapFromGeoJsonBuildsUsableMap(t *testing.T) {
	m, err := NewMapFromGeoJson([]byte(sampleGeoJson))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.Polygon("area"); err != nil {
		t.Errorf("Polygon(area): %v", err)
	}
	if _, err := m.LineString("path"); err != nil {
		t.Errorf("LineString(path): %v", err)
	}
}

// TestNewMapFromGeoJsonInvalidJson checks that malformed GeoJSON input
// surfaces an error rather than returning a partially built map.
func TestNewMapFromGeoJsonInvalidJson(t *testing.T) {
	if _, err := NewMapFromGeoJson([]byte("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}
