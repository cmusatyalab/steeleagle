from __future__ import annotations

from shapely.geometry import Polygon


class Partition:
    """Abstract base: generate partitioned segments (planar coordinates, in meters)."""

    def generate_partitioned_geopoints(self, polygon: Polygon) -> list[list[tuple[float, float]]]:
        raise NotImplementedError
