from __future__ import annotations

from shapely.geometry import Polygon

from ..partition import Partition


class EdgePartition(Partition):
    def generate_partitioned_geopoints(self, polygon: Polygon) -> list[list[tuple[float, float]]]:
        return [[(x, y) for x, y, *_ in polygon.exterior.coords]]
