package geo

import (
	"strings"
	"testing"
)

// TestGetPolygonFound checks that GetPolygon returns the polygon stored
// under a matching key.
func TestGetPolygonFound(t *testing.T) {
	m := testMap()
	poly, err := m.GetPolygon("poly")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if poly.AsGeometry().IsEmpty() {
		t.Error("expected a non-empty polygon")
	}
}

// TestGetPolygonMissingKey checks that GetPolygon errors when the key
// isn't present in geometry.
func TestGetPolygonMissingKey(t *testing.T) {
	m := testMap()
	if _, err := m.GetPolygon("missing"); err == nil {
		t.Fatal("expected an error for a missing key")
	}
}

// TestGetPolygonWrongType checks that GetPolygon errors when the key maps
// to a geometry that isn't a polygon.
func TestGetPolygonWrongType(t *testing.T) {
	m := testMap()
	if _, err := m.GetPolygon("line"); err == nil {
		t.Fatal("expected an error for a key that isn't a polygon")
	}
}

// TestGetLineStringFound checks that GetLineString returns the line
// string stored under a matching key.
func TestGetLineStringFound(t *testing.T) {
	m := testMap()
	ls, err := m.GetLineString("line")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ls.AsGeometry().IsEmpty() {
		t.Error("expected a non-empty line string")
	}
}

// TestGetLineStringMissingKey checks that GetLineString errors when the
// key isn't present in geometry.
func TestGetLineStringMissingKey(t *testing.T) {
	m := testMap()
	if _, err := m.GetLineString("missing"); err == nil {
		t.Fatal("expected an error for a missing key")
	}
}

// TestGetLineStringWrongType checks that GetLineString errors when the
// key maps to a geometry that isn't a line string.
func TestGetLineStringWrongType(t *testing.T) {
	m := testMap()
	if _, err := m.GetLineString("poly"); err == nil {
		t.Fatal("expected an error for a key that isn't a line string")
	}
}

// TestNewMapIsEmpty checks that NewMap returns a usable map with no
// geometry in it.
func TestNewMapIsEmpty(t *testing.T) {
	m := NewMap()
	if _, err := m.GetPolygon("anything"); err == nil {
		t.Fatal("expected an error looking up a polygon in an empty map")
	}
}

// TestNewMapFromGeoJSONBuildsUsableMap checks that a map built directly
// from GeoJSON data can be queried via GetPolygon/GetLineString.
func TestNewMapFromGeoJSONBuildsUsableMap(t *testing.T) {
	m, err := NewMapFromGeoJSON(strings.NewReader(sampleGeoJSON))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := m.GetPolygon("area"); err != nil {
		t.Errorf("GetPolygon(area): %v", err)
	}
	if _, err := m.GetLineString("path"); err != nil {
		t.Errorf("GetLineString(path): %v", err)
	}
}

// TestNewMapFromGeoJSONInvalidJSON checks that malformed GeoJSON input
// surfaces an error rather than returning a partially built map.
func TestNewMapFromGeoJSONInvalidJSON(t *testing.T) {
	if _, err := NewMapFromGeoJSON(strings.NewReader("not json")); err == nil {
		t.Fatal("expected an error for invalid JSON")
	}
}
