package geo

import (
	"fmt"
	"math"
	"slices"
	"sort"

	"github.com/cmusatyalab/steeleagle/sdk/dsl/types"
	"github.com/peterstace/simplefeatures/carto"
	"github.com/peterstace/simplefeatures/geom"
)

// rotate rotates a point by an angle.
func rotate(p geom.XY, angle float64) geom.XY {
	sin, cos := math.Sin(angle), math.Cos(angle)
	return geom.XY{X: p.X*cos - p.Y*sin, Y: p.X*sin + p.Y*cos}
}

// addPoints concatenates geom points together either in forward
// order or in reverse.
func addPoints(points []types.GlobalPosition, newPoints []geom.XY, proj *carto.UTM, angle float64, alt float32, reverse bool) []types.GlobalPosition {
	if reverse {
		slices.Reverse(newPoints)
	}
	newPositions := make([]types.GlobalPosition, len(newPoints))
	for i, p := range newPoints {
		unrotated := rotate(p, -angle) // undo the rotation first
		lonlat := proj.Reverse(unrotated)
		newPositions[i] = types.GlobalPosition{
			Latitude:  lonlat.Y,
			Longitude: lonlat.X,
			Altitude:  alt,
		}
		if i >= 1 { // set heading if it isn't the first point
			hdg := Bearing(newPositions[i-1], newPositions[i])
			newPositions[i].Heading = hdg
		}
	}
	return append(points, newPositions...)
}

// sortLineStrings sorts several line strings by their minimum X
// value, effectively sorting them from West to East.
func sortLineStrings(lines []geom.LineString) []geom.LineString {
	sort.Slice(lines, func(i, j int) bool {
		return minX(lines[i]) < minX(lines[j])
	})
	return lines
}

// minX gets the minimum X value of a line string sequence.
func minX(ls geom.LineString) float64 {
	seq := ls.Coordinates()
	a, b := seq.GetXY(0), seq.GetXY(seq.Length()-1)
	return math.Min(a.X, b.X)
}

// locateOnLine finds the segment of a coordinate list that contains
// a point, returning the enclosing indices and the points at those
// indices.
func locateOnLine(coords geom.Sequence, p geom.XY) (int, int, geom.XY, geom.XY, error) {
	// Iterate through all the points and perform colinearity check
	for i := 0; i < coords.Length()-1; i++ {
		a, b := coords.GetXY(i), coords.GetXY(i+1)
		ab := b.Sub(a)
		ap := p.Sub(a)
		l := ab.Length()
		if l == 0 {
			continue // repeated point on the polygon
		}
		// Point intersections are not perfect, need to check if
		// the point is close enough to the segment
		if math.Abs(ab.Cross(ap))/l > 1e-6 {
			continue // point is too far away, check next
		}
		return i, i + 1, coords.GetXY(i), coords.GetXY(i + 1), nil
	}
	return 0, 0, geom.XY{}, geom.XY{}, fmt.Errorf("point doesn't lie on perimeter")
}

// getSection finds the length of a subsection of a coordinate list,
// and returns that subsection.
func getSection(coords geom.Sequence, startIdx, endIdx int) ([]geom.XY, float64) {
	distance := 0.0
	section := []geom.XY{coords.GetXY(startIdx)}
	for i := startIdx; i != endIdx; i = (i + 1) % coords.Length() {
		a, b := coords.GetXY(i), coords.GetXY((i+1)%coords.Length())
		ab := b.Sub(a)
		distance = distance + ab.Length()
		section = append(section, b)
	}
	return section, distance
}

// Bearing returns the great-circle compass bearing between from
// and to.
func Bearing(from, to types.GlobalPosition) float32 {
	psi1 := from.Latitude * math.Pi / 180
	psi2 := to.Latitude * math.Pi / 180
	delta := (to.Longitude - from.Longitude) * math.Pi / 180
	y := math.Sin(delta) * math.Cos(psi2)
	x := math.Cos(psi1)*math.Sin(psi2) - math.Sin(psi1)*math.Cos(psi2)*math.Cos(delta)
	theta := math.Atan2(y, x)
	return float32(math.Mod(theta*180/math.Pi+360, 360))
}
