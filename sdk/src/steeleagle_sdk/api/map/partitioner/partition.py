from __future__ import annotations

from shapely.geometry import Polygon

from .geopoints import GeoPoints


class Partition:
    """Abstract base: generate partitioned GeoPoints (planar coordinates)."""

    def generate_partitioned_geopoints(self, polygon: Polygon) -> list[GeoPoints]:
        raise NotImplementedError
