package geo

import (
	"fmt"

	"github.com/cmusatyalab/steeleagle/sdk/params"
	"github.com/peterstace/simplefeatures/geom"
)

// corridorCompatible are types that are compatible with a corridor scan.
type corridorCompatible interface {
	params.LineString | params.MultiLineString | params.Polygon
}

// CorridorScan lists out the vertices of a lon/lat feature as GeoPoint types
// for point-by-point traversal. Polygons yield their exterior ring, line
// strings yield their points in order, and multi line strings yield the
// points of each line string in order, one after another.
func CorridorScan[T corridorCompatible](m *Map, area T, altitude float32) ([]GeoPoint, error) {
	var seqs []geom.Sequence
	switch a := any(area).(type) {
	case params.Polygon:
		poly, err := m.Polygon(a)
		if err != nil {
			return nil, err
		}
		seqs = append(seqs, poly.ExteriorRing().Coordinates())
	case params.LineString:
		ls, err := m.LineString(a)
		if err != nil {
			return nil, err
		}
		seqs = append(seqs, ls.Coordinates())
	case params.MultiLineString:
		mls, err := m.MultiLineString(a)
		if err != nil {
			return nil, err
		}
		for i := 0; i < mls.NumLineStrings(); i++ {
			seqs = append(seqs, mls.LineStringN(i).Coordinates())
		}
	default:
		return nil, fmt.Errorf("unsupported corridor area type %T", area)
	}
	return sequencesToPoints(seqs, altitude), nil
}

// sequencesToPoints flattens coordinate sequences into GeoPoints at the given
// altitude, setting each point's heading to the bearing from the previous one.
func sequencesToPoints(seqs []geom.Sequence, altitude float32) []GeoPoint {
	var points []GeoPoint
	for _, seq := range seqs {
		for i := 0; i < seq.Length(); i++ {
			xy := seq.GetXY(i)
			p := GeoPoint{
				Longitude: xy.X,
				Latitude:  xy.Y,
				Altitude:  altitude,
			}
			if n := len(points); n >= 1 { // set heading if it isn't the first point
				p.Heading = Bearing(points[n-1], p)
			}
			points = append(points, p)
		}
	}
	return points
}
