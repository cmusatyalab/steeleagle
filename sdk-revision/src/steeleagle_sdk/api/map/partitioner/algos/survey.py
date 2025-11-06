from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
from shapely.geometry import Point, LineString, Polygon
from ..partition import Partition
from ..geopoints import GeoPoints
from ..utils import rotated_infinite_transects, line_polygon_intersection_points, round_xy

@dataclass
class SurveyPartition(Partition):
    spacing: float
    angle_degrees: float
    trigger_distance: float

    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        results: List[GeoPoints] = []
        for line in rotated_infinite_transects(polygon, self.spacing, self.angle_degrees):
            pts = line_polygon_intersection_points(line, polygon)
            if len(pts) >= 2:
                for a, b in zip(pts[0::2], pts[1::2]):
                    ax, ay = a
                    bx, by = b
                    seg = LineString([a, b])
                    length = seg.length
                    if length <= 0.0:
                        continue
                    ux, uy = (bx - ax) / length, (by - ay) / length
                    npts = max(1, int(length // self.trigger_distance))
                    line_points: List[Tuple[float, float]] = []
                    for i in range(npts + 1):
                        d = i * self.trigger_distance
                        px = ax + d * ux
                        py = ay + d * uy
                        p = Point(px, py)
                        if polygon.covers(p):
                            line_points.append(round_xy(px, py, 3))
                    if line_points:
                        results.append(GeoPoints(line_points))
        return results
