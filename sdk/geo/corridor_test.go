package geo

import (
	"testing"
)

// TestCorridorScanMissingArea checks that CorridorScan surfaces an error
// when the requested area key isn't present in the map's geometry.
func TestCorridorScanMissingArea(t *testing.T) {
	m := testMap()
	if _, err := m.CorridorScan("missing", 0); err == nil {
		t.Fatal("expected an error for a missing area key")
	}
}

// TestCorridorScanAreaNotPolygon checks that CorridorScan errors when the
// area key maps to a non-polygon geometry.
func TestCorridorScanAreaNotPolygon(t *testing.T) {
	m := testMap()
	if _, err := m.CorridorScan("line", 0); err == nil {
		t.Fatal("expected an error for a non-polygon area")
	}
}

// TestCorridorScanReturnsOneVertexPerCoordinate checks that CorridorScan
// returns exactly one GeoPoint per exterior-ring coordinate, in ring order,
// with no extra or missing entries.
func TestCorridorScanReturnsOneVertexPerCoordinate(t *testing.T) {
	m := testMap() // "poly" ring: (0,0), (0,10), (10,10), (10,0), (0,0)
	points, err := m.CorridorScan("poly", 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	want := [][2]float64{{0, 0}, {0, 10}, {10, 10}, {10, 0}, {0, 0}}
	if len(points) != len(want) {
		t.Fatalf("expected %d points, got %d", len(want), len(points))
	}
	for i, w := range want {
		if points[i].Longitude != w[0] || points[i].Latitude != w[1] {
			t.Errorf("point %d: got (lon=%v,lat=%v), want (lon=%v,lat=%v)",
				i, points[i].Longitude, points[i].Latitude, w[0], w[1])
		}
	}
}

// TestCorridorScanSetsAltitude checks that every returned point carries the
// requested altitude.
func TestCorridorScanSetsAltitude(t *testing.T) {
	m := testMap()
	points, err := m.CorridorScan("poly", 75)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for i, p := range points {
		if p.Altitude != 75 {
			t.Errorf("point %d: expected altitude 75, got %v", i, p.Altitude)
		}
	}
}

// TestCorridorScanSetsHeadings checks that the first point has a zero-value
// heading and that every subsequent point's heading is the bearing from the
// previous point to it.
func TestCorridorScanSetsHeadings(t *testing.T) {
	m := testMap()
	points, err := m.CorridorScan("poly", 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(points) == 0 {
		t.Fatal("expected at least one point")
	}
	if points[0].Heading != 0 {
		t.Errorf("expected first point to have zero-value heading, got %v", points[0].Heading)
	}
	for i := 1; i < len(points); i++ {
		want := Bearing(points[i-1], points[i])
		if points[i].Heading != want {
			t.Errorf("point %d: expected heading %v, got %v", i, want, points[i].Heading)
		}
	}
}
