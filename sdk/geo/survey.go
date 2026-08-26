package geo

import (
	"fmt"
	"math"
	"slices"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/carto"
	"github.com/peterstace/simplefeatures/geom"
)

// SurveyScan computes a survey pattern over a WGS84 lon/lat polygon.
// Spacing is the distance in meters between scan lines, and heading is
// the heading of each survey corridor.
func (m *Map) SurveyScan(area params.MapFeature, spacing, heading, altitude float32) ([]GeoPoint, error) {
	if spacing <= 0 {
		return nil, fmt.Errorf("spacing must be positive")
	}
	// Convert heading to an angle
	angle := (90 - float64(heading)) * math.Pi / 180

	// Retrieve polygon from store
	poly, err := m.GetPolygon(area)
	if err != nil {
		return nil, err
	}

	// Create projector object using the polygon's first vertex as the
	// reference point for the UTM zone
	proj, err := carto.NewUTMFromLocation(poly.ExteriorRing().Coordinates().GetXY(0))
	if err != nil {
		return nil, err
	}

	// Transform the polygon into the projected, rotated coordinate space
	rotated := poly.AsGeometry().TransformXY(func(p geom.XY) geom.XY {
		return rotate(proj.Forward(p), angle)
	})

	minXY, maxXY, ok := rotated.Envelope().MinMaxXYs()
	if !ok {
		return nil, fmt.Errorf("polygon has an empty envelope")
	}
	pad := maxXY.X - minXY.X + 1

	// Need to rotate polygon to same coordinate space
	rotatedPoly, ok := rotated.AsPolygon()
	if !ok {
		return nil, fmt.Errorf("rotated geometry is not a polygon")
	}
	coords := rotatedPoly.ExteriorRing().Coordinates()

	var points []GeoPoint
	reverse := false // we want to fly the next corridor in reverse
	for y := minXY.Y + float64(spacing)/2; y <= maxXY.Y; y += float64(spacing) {
		line := geom.NewLineStringXY(minXY.X-pad, y, maxXY.X+pad, y).AsGeometry()
		inter, err := geom.Intersection(line, rotated)
		if err != nil {
			return nil, err
		}

		// Get points at the intersection between the survey corridor
		// and the polygon
		var lineParts []geom.LineString
		for _, part := range inter.Dump() {
			ls, ok := part.AsLineString()
			if !ok { // if a point intersection occurs, skip it
				continue
			}
			lineParts = append(lineParts, ls)
		}
		sorted := sortLineStrings(lineParts)
		for i, ls := range sorted {
			seq := ls.Coordinates()
			a, b := seq.GetXY(0), seq.GetXY(seq.Length()-1)
			points = addPoints(points, []geom.XY{a, b}, proj, angle, altitude, reverse)
			if i < len(sorted)-1 { // multi-line case
				// Reset points to be end of this line and start of the next
				a = b
				b = sorted[i+1].Coordinates().GetXY(0)
				// Locate the points on the polygon and calculate the fastest transit
				// path along the perimeter to reach the next one
				a1, a2, a1c, a2c, err := locateOnLine(coords, a)
				if err != nil {
					return nil, fmt.Errorf("intersection point was not on perimeter")
				}
				b1, b2, b1c, b2c, err := locateOnLine(coords, b)
				if err != nil {
					return nil, fmt.Errorf("intersection point was not on perimeter")
				}
				newPoints := []geom.XY{}
				rSec, rLen := getSection(coords, b2, a1)
				rLen = rLen + b2c.Sub(b).Length() + a.Sub(a1c).Length()
				fSec, fLen := getSection(coords, a2, b1)
				fLen = fLen + a2c.Sub(a).Length() + b.Sub(b1c).Length()
				if fLen < rLen {
					newPoints = append(newPoints, a)
					newPoints = append(newPoints, fSec...)
					newPoints = append(newPoints, b)
					points = addPoints(points, newPoints, proj, angle, altitude, reverse)
				} else {
					slices.Reverse(rSec)
					newPoints = append(newPoints, a)
					newPoints = append(newPoints, rSec...)
					newPoints = append(newPoints, b)
					points = addPoints(points, newPoints, proj, angle, altitude, reverse)
				}
			}
		}
		reverse = !reverse
	}
	return points, nil
}
