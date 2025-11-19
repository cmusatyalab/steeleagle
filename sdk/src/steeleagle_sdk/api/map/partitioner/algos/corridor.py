from __future__ import annotations
from dataclasses import dataclass
from typing import List
from shapely.geometry import Polygon
from ..partition import Partition
from ..geopoints import GeoPoints
from ..utils import rotated_infinite_transects, line_polygon_intersection_points, round_xy

@dataclass
class CorridorPartition(Partition):
    spacing: float
    angle_degrees: float

    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        results: List[GeoPoints] = []
        for line in rotated_infinite_transects(polygon, self.spacing, self.angle_degrees):
            pts = line_polygon_intersection_points(line, polygon)
            if len(pts) >= 2:
                for a, b in zip(pts[0::2], pts[1::2]):
                    p0 = round_xy(a[0], a[1])
                    p1 = round_xy(b[0], b[1])
                    results.append(GeoPoints([p0, p1, p0]))  # mimic [start, end, start]
        return results
