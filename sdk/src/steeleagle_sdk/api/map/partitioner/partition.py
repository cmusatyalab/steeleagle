from __future__ import annotations
from typing import List
from shapely.geometry import Polygon
from .geopoints import GeoPoints

class Partition:
    """Abstract base: generate partitioned GeoPoints (planar coordinates)."""
    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        raise NotImplementedError
