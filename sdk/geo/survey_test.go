package geo

import (
	"math"
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/carto"
	"github.com/peterstace/simplefeatures/geom"
)

// TestSurveyScanRejectsNonPositiveSpacing checks that SurveyScan validates
// its spacing argument before doing any geometric work.
func TestSurveyScanRejectsNonPositiveSpacing(t *testing.T) {
	m := &Map{
		geometry: map[params.MapFeature]geom.Geometry{},
	}
	for _, spacing := range []float32{0, -1} {
		_, err := m.SurveyScan("area", spacing, 0, 0)
		if err == nil || !strings.Contains(err.Error(), "spacing must be positive") {
			t.Errorf("spacing=%v: expected 'spacing must be positive' error, got %v", spacing, err)
		}
	}
}

// TestSurveyScanMissingArea checks that SurveyScan surfaces an error when
// the requested area key isn't present in the map's geometry.
func TestSurveyScanMissingArea(t *testing.T) {
	m := &Map{
		geometry: map[params.MapFeature]geom.Geometry{},
	}
	if _, err := m.SurveyScan("missing", 10, 0, 0); err == nil {
		t.Fatal("expected an error for a missing area key")
	}
}

// TestSurveyScanAreaNotPolygon checks that SurveyScan errors when the area
// key maps to a non-polygon geometry.
func TestSurveyScanAreaNotPolygon(t *testing.T) {
	line := geom.NewLineStringXY(-79.9, 40.4, -79.8, 40.4)
	m := &Map{
		geometry: map[params.MapFeature]geom.Geometry{
			"area": line.AsGeometry(),
		},
	}
	if _, err := m.SurveyScan("area", 10, 0, 0); err == nil {
		t.Fatal("expected an error for a non-polygon area")
	}
}

// TestSurveyScanConvexRectangleBoustrophedon checks the baseline scan
// pattern over a simple convex polygon: each row should be a single leg,
// and consecutive rows should alternate direction (boustrophedon / "lawn
// mower" pattern).
func TestSurveyScanConvexRectangleBoustrophedon(t *testing.T) {
	base := geom.XY{X: -79.9, Y: 40.4}
	verts := [][2]float64{{0, 0}, {0, 4}, {6, 4}, {6, 0}, {0, 0}}

	proj, err := carto.NewUTMFromLocation(base)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	pv := projectNiceVerts(proj, base, verts[:4])
	ymin, ymax := envelopeY(pv)
	spacing := float32((ymax - ymin) / 3)

	poly := buildNicePolygon(base, verts)
	m := &Map{
		geometry: map[params.MapFeature]geom.Geometry{
			"area": poly.AsGeometry(),
		},
	}

	points, err := m.SurveyScan("area", spacing, 90, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(points) != 6 {
		t.Fatalf("expected 6 points (3 rows x 2 endpoints), got %d", len(points))
	}

	if points[0].Longitude >= points[1].Longitude {
		t.Errorf("expected row 0 to fly west to east, got lon %v -> %v", points[0].Longitude, points[1].Longitude)
	}
	if points[2].Longitude <= points[3].Longitude {
		t.Errorf("expected row 1 to fly east to west, got lon %v -> %v", points[2].Longitude, points[3].Longitude)
	}
	if points[4].Longitude >= points[5].Longitude {
		t.Errorf("expected row 2 to fly west to east, got lon %v -> %v", points[4].Longitude, points[5].Longitude)
	}

	row0Y := toXY(proj, points[0]).Y
	row1Y := toXY(proj, points[2]).Y
	if diff := math.Abs(row1Y-row0Y) - float64(spacing); math.Abs(diff) > 0.5 {
		t.Errorf("expected row spacing ~%v meters, got %v", spacing, row1Y-row0Y)
	}
}

// TestSurveyScanConcaveRoutesThroughShortConnector checks the primary
// concave-polygon requirement: when a scan row crosses a concave notch as
// two disjoint line segments, SurveyScan must connect them by traveling
// along the polygon's own perimeter rather than cutting straight across
// the (empty) notch.
//
//	(0,3)---(1,3)     (4,3)---(5,3)
//	  |        \       /        |
//	  |         (1,1)-(4,1)     |     <- row 1.5 sits above this connector
//	  |                          |
//	(0,0)--------------------(5,0)
//
// A scan row at nice-y=1.5 crosses only the two prongs (x in [0,1] and
// x in [4,5]); the shortest perimeter path between them runs down to the
// connector at y=1 and back up, which is what should be returned.
func TestSurveyScanConcaveRoutesThroughShortConnector(t *testing.T) {
	base := geom.XY{X: -79.9, Y: 40.4}
	verts := [][2]float64{
		{0, 0}, {0, 3}, {1, 3}, {1, 1}, {4, 1}, {4, 3}, {5, 3}, {5, 0}, {0, 0},
	}
	uniqueVerts := verts[:8]

	proj, err := carto.NewUTMFromLocation(base)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	pv := projectNiceVerts(proj, base, uniqueVerts)
	ymin, ymax := envelopeY(pv)

	// Row sits 25% of the way up from the connector (index 3, (1,1)) to
	// the prong top (index 2, (1,3)), matching nice-y=1.5
	const t0 = 0.25
	expectedA := lerp(pv[3], pv[2], t0) // on the left prong's inner edge
	rowY := expectedA.Y
	tb := solveT(pv[4], pv[5], rowY)
	expectedB := lerp(pv[4], pv[5], tb) // on the right prong's inner edge
	expectedLeftOuter := lerp(pv[0], pv[1], solveT(pv[0], pv[1], rowY))
	expectedRightOuter := lerp(pv[7], pv[6], solveT(pv[7], pv[6], rowY))

	spacing := 2 * (rowY - ymin)
	if secondRow := ymin + 1.5*spacing; secondRow <= ymax {
		t.Fatalf("test setup invalid: expected only one sampled row, but a second row at %v would fall within [%v,%v]", secondRow, ymin, ymax)
	}

	poly := buildNicePolygon(base, verts)
	m := &Map{
		geometry: map[params.MapFeature]geom.Geometry{
			"area": poly.AsGeometry(),
		},
	}

	points, err := m.SurveyScan("area", float32(spacing), 90, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(points) != 8 {
		t.Fatalf("expected 8 points (2 + 4 transit + 2), got %d", len(points))
	}

	const tol = 1e-2 // meters; accounts for float32 spacing rounding
	want := []geom.XY{
		expectedLeftOuter,
		expectedA,
		expectedA,
		pv[3], // connector corner (1,1)
		pv[4], // connector corner (4,1)
		expectedB,
		expectedB,
		expectedRightOuter,
	}
	for i, w := range want {
		requireXY(t, toXY(proj, points[i]), w, tol, "point "+string(rune('0'+i)))
	}
}

// TestSurveyScanConcaveRoutesAroundOutside checks the other branch of the
// perimeter routing decision: when going through the direct connector
// would be the *longer* way around, SurveyScan should route around the
// outside of the polygon instead.
//
//	(0,1.3)-(0.1,1.3)                     (0.4,1.3)-(0.5,1.3)
//	   |        \                           /        |
//	   |         |                         |         |     <- row 1.15 crosses only
//	   |         |   (0.2,0.9)-(0.3,0.9)   |         |        these two outer teeth
//	   |         |    /              \     |         |
//	   |     (0.1,0.1)-(0.2,0.1) (0.3,0.1)-(0.4,0.1)  |
//	   |                                               |
//	 (0,0)----------------------------------------(0.5,0)
//
// A scan row at nice-y=1.15 sits above the middle tooth's top (0.9) but
// below the outer teeth's tops (1.3), crossing only the left and right
// prongs.
func TestSurveyScanConcaveRoutesAroundOutside(t *testing.T) {
	base := geom.XY{X: -79.9, Y: 40.4}
	verts := [][2]float64{
		{0, 0}, {0, 1.3}, {0.1, 1.3}, {0.1, 0.1},
		{0.2, 0.1}, {0.2, 0.9}, {0.3, 0.9}, {0.3, 0.1},
		{0.4, 0.1}, {0.4, 1.3}, {0.5, 1.3}, {0.5, 0},
		{0, 0},
	}
	uniqueVerts := verts[:12]

	proj, err := carto.NewUTMFromLocation(base)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	pv := projectNiceVerts(proj, base, uniqueVerts)
	ymin, ymax := envelopeY(pv)

	// Row sits 87.5% of the way up from the base (index 3) to the outer
	// tooth top (index 2), matching nice-y=1.15 (well above the middle
	// tooth's top at nice-y=0.9)
	const t0 = 0.875
	expectedA := lerp(pv[3], pv[2], t0)
	rowY := expectedA.Y
	tb := solveT(pv[8], pv[9], rowY)
	expectedB := lerp(pv[8], pv[9], tb)
	expectedLeftOuter := lerp(pv[0], pv[1], solveT(pv[0], pv[1], rowY))
	expectedRightOuter := lerp(pv[11], pv[10], solveT(pv[11], pv[10], rowY))

	spacing := 2 * (rowY - ymin)
	if secondRow := ymin + 1.5*spacing; secondRow <= ymax {
		t.Fatalf("test setup invalid: expected only one sampled row, but a second row at %v would fall within [%v,%v]", secondRow, ymin, ymax)
	}

	poly := buildNicePolygon(base, verts)
	m := &Map{
		geometry: map[params.MapFeature]geom.Geometry{
			"area": poly.AsGeometry(),
		},
	}

	points, err := m.SurveyScan("area", float32(spacing), 90, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(points) != 13 {
		t.Fatalf("expected 13 points (2 + 9 transit + 2), got %d", len(points))
	}

	const tol = 1e-2 // meters; accounts for float32 spacing rounding
	want := []geom.XY{
		expectedLeftOuter,
		expectedA,
		expectedA,
		pv[2],  // (0.1,1.3) - top of left tooth's inner edge
		pv[1],  // (0,1.3)   - top of left tooth's outer edge
		pv[0],  // (0,0)     - bottom left corner
		pv[0],  // ring-closure duplicate of (0,0)
		pv[11], // (0.5,0)   - bottom right corner
		pv[10], // (0.5,1.3) - top of right tooth's outer edge
		pv[9],  // (0.4,1.3) - top of right tooth's inner edge
		expectedB,
		expectedB,
		expectedRightOuter,
	}
	for i, w := range want {
		requireXY(t, toXY(proj, points[i]), w, tol, "point "+string(rune('0'+i%10))+string(rune('0'+i/10)))
	}
}
