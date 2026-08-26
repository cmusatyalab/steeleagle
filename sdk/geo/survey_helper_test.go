package geo

import (
	"github.com/peterstace/simplefeatures/carto"
	"github.com/peterstace/simplefeatures/geom"
)

// niceScale converts small, easy-to-reason-about "nice unit" coordinates
// into real WGS84 lon/lat offsets from a base point, so test polygons can
// be designed with simple round numbers while still exercising the real
// UTM projection SurveyScan uses internally.
const niceScale = 0.0005

// buildNicePolygon converts a closed ring of [x,y] "nice unit" vertices
// into a WGS84 polygon offset from base.
func buildNicePolygon(base geom.XY, verts [][2]float64) geom.Polygon {
	flat := make([]float64, 0, len(verts)*2)
	for _, v := range verts {
		flat = append(flat, base.X+v[0]*niceScale, base.Y+v[1]*niceScale)
	}
	return geom.NewSingleRingPolygonXY(flat...)
}

// projectNiceVerts projects each "nice unit" vertex (via the same base/scale
// used by buildNicePolygon) through proj.Forward, mirroring the UTM
// coordinates SurveyScan computes internally for the polygon's vertices.
func projectNiceVerts(proj *carto.UTM, base geom.XY, verts [][2]float64) []geom.XY {
	out := make([]geom.XY, len(verts))
	for i, v := range verts {
		lonlat := geom.XY{X: base.X + v[0]*niceScale, Y: base.Y + v[1]*niceScale}
		out[i] = proj.Forward(lonlat)
	}
	return out
}

// lerp linearly interpolates between two projected points.
func lerp(p1, p2 geom.XY, t float64) geom.XY {
	return geom.XY{X: p1.X + t*(p2.X-p1.X), Y: p1.Y + t*(p2.Y-p1.Y)}
}

// solveT finds the interpolation parameter t such that lerp(p1,p2,t).Y == y.
func solveT(p1, p2 geom.XY, y float64) float64 {
	return (y - p1.Y) / (p2.Y - p1.Y)
}

// toXY re-projects a returned GeoPoint back into the same UTM space
// used to build expectations, so returned points can be compared exactly
// against hand-derived projected coordinates.
func toXY(proj *carto.UTM, gp GeoPoint) geom.XY {
	return proj.Forward(geom.XY{X: gp.Longitude, Y: gp.Latitude})
}

// envelope finds the outer bounds of a list of points.
func envelopeY(pts []geom.XY) (min, max float64) {
	min, max = pts[0].Y, pts[0].Y
	for _, p := range pts[1:] {
		if p.Y < min {
			min = p.Y
		}
		if p.Y > max {
			max = p.Y
		}
	}
	return min, max
}
