from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon

from ..geopoints import GeoPoints
from ..partition import Partition
from ..utils import (
    line_polygon_intersection_points,
    rotated_infinite_transects,
    round_xy,
)


@dataclass
class CorridorPartition(Partition):
    spacing: float
    angle_degrees: float

    def generate_partitioned_geopoints(self, polygon: Polygon) -> list[GeoPoints]:
        results: list[GeoPoints] = []
        for line in rotated_infinite_transects(
            polygon, self.spacing, self.angle_degrees
        ):
            pts = line_polygon_intersection_points(line, polygon)
            if len(pts) >= 2:
                for a, b in zip(pts[0::2], pts[1::2]):
                    p0 = round_xy(a[0], a[1])
                    p1 = round_xy(b[0], b[1])
                    results.append(GeoPoints([p0, p1, p0]))  # mimic [start, end, start]
        return results
