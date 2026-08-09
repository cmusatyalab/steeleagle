from __future__ import annotations

from shapely.geometry import Polygon

from ..partition import Partition


class EdgePartition(Partition):
    def generate_partitioned_geopoints(self, polygon: Polygon) -> list[list[tuple[float, float]]]:
        coords = list(polygon.exterior.coords)
        pairs = []
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            pairs.append([(p1[0], p1[1]), (p2[0], p2[1])])
        return pairs
