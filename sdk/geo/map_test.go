package geo

import (
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
// isn't present in placemarks.
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
// key isn't present in placemarks.
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
