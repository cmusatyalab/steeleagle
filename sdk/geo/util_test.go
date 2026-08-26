package geo

import (
	"math"
	"testing"

	"github.com/peterstace/simplefeatures/carto"
	"github.com/peterstace/simplefeatures/geom"
)

// epsilon for float comparison.
const epsilon = 1e-9

// TestRotateIdentity checks that rotating by zero radians is a no-op.
func TestRotateIdentity(t *testing.T) {
	p := geom.XY{X: 3, Y: -4}
	got := rotate(p, 0)
	requireXY(t, got, p, epsilon, "rotate by 0")
}

// TestRotateQuarterTurns checks rotation by +/-90 degrees against
// hand-computed results.
func TestRotateQuarterTurns(t *testing.T) {
	p := geom.XY{X: 1, Y: 0}

	got := rotate(p, math.Pi/2)
	requireXY(t, got, geom.XY{X: 0, Y: 1}, epsilon, "rotate +90")

	got = rotate(p, -math.Pi/2)
	requireXY(t, got, geom.XY{X: 0, Y: -1}, epsilon, "rotate -90")
}

// TestRotateRoundTrip checks that rotating by an angle and then by its
// negation recovers the original point, for an arbitrary angle.
func TestRotateRoundTrip(t *testing.T) {
	p := geom.XY{X: 12.5, Y: -7.25}
	angle := 37 * math.Pi / 180
	got := rotate(rotate(p, angle), -angle)
	requireXY(t, got, p, 1e-9, "rotate round trip")
}

// TestAddPointsForward checks that addPoints appends projected points in
// forward order, sets no heading on the first point, and sets a bearing
// derived heading on subsequent points.
func TestAddPointsForward(t *testing.T) {
	proj, err := carto.NewUTMFromLocation(geom.XY{X: -81, Y: 40})
	if err != nil {
		t.Fatalf("unexpected error building projector: %v", err)
	}
	base := proj.Forward(geom.XY{X: -81, Y: 40})
	p0 := base
	p1 := geom.XY{X: base.X, Y: base.Y + 1000} // 1000m due grid-north of p0

	existing := []GeoPoint{{Latitude: 1, Longitude: 2}}
	got := addPoints(existing, []geom.XY{p0, p1}, proj, 0, 50, false)

	if len(got) != 3 {
		t.Fatalf("expected 3 points, got %d", len(got))
	}
	if got[0].Latitude != 1 || got[0].Longitude != 2 {
		t.Errorf("existing point was mutated: %+v", got[0])
	}

	wantP0 := proj.Reverse(p0)
	if math.Abs(got[1].Longitude-wantP0.X) > 1e-6 || math.Abs(got[1].Latitude-wantP0.Y) > 1e-6 {
		t.Errorf("point 1 lon/lat mismatch: got (%v,%v) want (%v,%v)", got[1].Longitude, got[1].Latitude, wantP0.X, wantP0.Y)
	}
	if got[1].Altitude != 50 {
		t.Errorf("expected altitude 50, got %v", got[1].Altitude)
	}
	if got[1].Heading != 0 {
		t.Errorf("expected first point to have zero-value heading, got %v", got[1].Heading)
	}

	// p1 is due grid-north of p0 on the central meridian, so the bearing
	// from p0 to p1 should be ~0 degrees (true north)
	if got[2].Heading > 0.01 && got[2].Heading < 359.99 {
		t.Errorf("expected heading ~0 (north), got %v", got[2].Heading)
	}
}

// TestAddPointsReverse checks that addPoints reverses the supplied points
// before appending them and computes headings in the resulting order.
func TestAddPointsReverse(t *testing.T) {
	proj, err := carto.NewUTMFromLocation(geom.XY{X: -81, Y: 40})
	if err != nil {
		t.Fatalf("unexpected error building projector: %v", err)
	}
	base := proj.Forward(geom.XY{X: -81, Y: 40})
	p0 := base
	p1 := geom.XY{X: base.X, Y: base.Y + 1000}

	got := addPoints(nil, []geom.XY{p0, p1}, proj, 0, 10, true)
	if len(got) != 2 {
		t.Fatalf("expected 2 points, got %d", len(got))
	}

	wantFirst := proj.Reverse(p1)
	if math.Abs(got[0].Longitude-wantFirst.X) > 1e-6 || math.Abs(got[0].Latitude-wantFirst.Y) > 1e-6 {
		t.Errorf("expected first returned point to be the original last point; got (%v,%v) want (%v,%v)",
			got[0].Longitude, got[0].Latitude, wantFirst.X, wantFirst.Y)
	}

	// Second point (p0) is due grid-south of the first (p1), so its
	// heading should be ~180 degrees
	if math.Abs(float64(got[1].Heading)-180) > 0.01 {
		t.Errorf("expected heading ~180 (south), got %v", got[1].Heading)
	}
}

// TestSortLineStringsWestToEast checks that line strings are ordered by
// their minimum X coordinate, regardless of insertion order.
func TestSortLineStringsWestToEast(t *testing.T) {
	east := geom.NewLineStringXY(10, 0, 12, 0)
	west := geom.NewLineStringXY(-5, 0, -3, 0)
	middle := geom.NewLineStringXY(2, 0, 4, 0)

	sorted := sortLineStrings([]geom.LineString{east, middle, west})
	if len(sorted) != 3 {
		t.Fatalf("expected 3 line strings, got %d", len(sorted))
	}
	if minX(sorted[0]) != -5 || minX(sorted[1]) != 2 || minX(sorted[2]) != 10 {
		t.Errorf("line strings not sorted west to east: minXs = %v, %v, %v",
			minX(sorted[0]), minX(sorted[1]), minX(sorted[2]))
	}
}

// TestMinXUsesEndpoints checks that minX considers only the two endpoints
// of the line string, matching how SurveyScan calls it on 2-point
// intersection segments.
func TestMinXUsesEndpoints(t *testing.T) {
	ls := geom.NewLineStringXY(7, 0, -2, 5)
	if got := minX(ls); got != -2 {
		t.Errorf("expected minX -2, got %v", got)
	}
}

// TestLocateOnLineFindsSegment checks that locateOnLine returns the
// enclosing segment for a point on the middle of an edge.
func TestLocateOnLineFindsSegment(t *testing.T) {
	coords := geom.NewLineStringXY(0, 0, 0, 10, 10, 10, 10, 0, 0, 0).Coordinates()

	i, j, a, b, err := locateOnLine(coords, geom.XY{X: 0, Y: 5})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if i != 0 || j != 1 {
		t.Errorf("expected indices 0,1, got %d,%d", i, j)
	}
	requireXY(t, a, geom.XY{X: 0, Y: 0}, epsilon, "segment start")
	requireXY(t, b, geom.XY{X: 0, Y: 10}, epsilon, "segment end")
}

// TestLocateOnLineAtVertex checks that a point exactly at a shared vertex
// resolves to the first colinear segment encountered during the scan.
func TestLocateOnLineAtVertex(t *testing.T) {
	coords := geom.NewLineStringXY(0, 0, 0, 10, 10, 10, 10, 0, 0, 0).Coordinates()

	i, j, _, _, err := locateOnLine(coords, geom.XY{X: 10, Y: 10})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if i != 1 || j != 2 {
		t.Errorf("expected indices 1,2, got %d,%d", i, j)
	}
}

// TestLocateOnLineNotOnPerimeter checks that an interior point (not on
// any edge) produces an error.
func TestLocateOnLineNotOnPerimeter(t *testing.T) {
	coords := geom.NewLineStringXY(0, 0, 0, 10, 10, 10, 10, 0, 0, 0).Coordinates()

	_, _, _, _, err := locateOnLine(coords, geom.XY{X: 5, Y: 5})
	if err == nil {
		t.Fatal("expected an error for a point not on the perimeter")
	}
}

// TestLocateOnLineSkipsRepeatedPoints checks that a zero-length segment
// (a repeated vertex) doesn't cause a division by zero and is simply
// skipped in favor of the next real segment.
func TestLocateOnLineSkipsRepeatedPoints(t *testing.T) {
	coords := geom.NewLineStringXY(0, 0, 0, 0, 0, 10, 10, 10, 10, 0, 0, 0).Coordinates()

	i, j, _, _, err := locateOnLine(coords, geom.XY{X: 0, Y: 5})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if i != 1 || j != 2 {
		t.Errorf("expected the repeated point at index 0 to be skipped, got indices %d,%d", i, j)
	}
}

// TestGetSectionDirect checks getSection over a simple forward range with
// no wraparound.
func TestGetSectionDirect(t *testing.T) {
	coords := geom.NewLineStringXY(0, 0, 0, 10, 10, 10, 10, 0, 0, 0).Coordinates()

	section, dist := getSection(coords, 0, 2)
	want := []geom.XY{{X: 0, Y: 0}, {X: 0, Y: 10}, {X: 10, Y: 10}}
	if dist != 20 {
		t.Errorf("expected distance 20, got %v", dist)
	}
	if len(section) != len(want) {
		t.Fatalf("expected %d points, got %d", len(want), len(section))
	}
	for i := range want {
		requireXY(t, section[i], want[i], epsilon, "section point")
	}
}

// TestGetSectionWraparound checks that getSection correctly wraps around
// the end of the coordinate list back to the start, which is exactly the
// case exercised when routing the perimeter of a concave polygon the
// "long way" around.
func TestGetSectionWraparound(t *testing.T) {
	coords := geom.NewLineStringXY(0, 0, 0, 10, 10, 10, 10, 0, 0, 0).Coordinates()

	// startIdx=3 ((10,0)) to endIdx=1 ((0,10)) requires wrapping past the
	// closing point at index 4 (which duplicates index 0)
	section, dist := getSection(coords, 3, 1)
	want := []geom.XY{{X: 10, Y: 0}, {X: 0, Y: 0}, {X: 0, Y: 0}, {X: 0, Y: 10}}
	if dist != 20 {
		t.Errorf("expected distance 20, got %v", dist)
	}
	if len(section) != len(want) {
		t.Fatalf("expected %d points, got %d", len(want), len(section))
	}
	for i := range want {
		requireXY(t, section[i], want[i], epsilon, "section point")
	}
}

// TestBearingCardinalDirections checks Bearing against hand-verified
// cardinal directions for small displacements.
func TestBearingCardinalDirections(t *testing.T) {
	origin := GeoPoint{Latitude: 0, Longitude: 0}

	cases := []struct {
		name string
		to   GeoPoint
		want float32
	}{
		{"north", GeoPoint{Latitude: 1, Longitude: 0}, 0},
		{"east", GeoPoint{Latitude: 0, Longitude: 1}, 90},
		{"south", GeoPoint{Latitude: -1, Longitude: 0}, 180},
		{"west", GeoPoint{Latitude: 0, Longitude: -1}, 270},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := Bearing(origin, tc.to)
			if math.Abs(float64(got-tc.want)) > 0.5 {
				t.Errorf("expected bearing ~%v, got %v", tc.want, got)
			}
		})
	}
}

// TestBearingSamePoint checks the degenerate case where from and to are
// identical, which should not produce NaN.
func TestBearingSamePoint(t *testing.T) {
	p := GeoPoint{Latitude: 12.3, Longitude: 45.6}
	got := Bearing(p, p)
	if got != 0 {
		t.Errorf("expected bearing 0 for identical points, got %v", got)
	}
}
