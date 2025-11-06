from __future__ import annotations
from typing import List
from shapely.geometry import Polygon
from ..partition import Partition
from ..geopoints import GeoPoints

class EdgePartition(Partition):
    
    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        coords = list(polygon.exterior.coords)
        pairs = []
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            pairs.append(GeoPoints([(p1[0], p1[1]), (p2[0], p2[1])]))
        return pairs
