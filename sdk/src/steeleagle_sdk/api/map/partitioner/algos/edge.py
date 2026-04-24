from __future__ import annotations

from shapely.geometry import Polygon

from ..geopoints import GeoPoints
from ..partition import Partition


class EdgePartition(Partition):
    def generate_partitioned_geopoints(self, polygon: Polygon) -> list[GeoPoints]:
        coords = list(polygon.exterior.coords)
        pairs = []
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            pairs.append(GeoPoints([(p1[0], p1[1]), (p2[0], p2[1])]))
        return pairs
