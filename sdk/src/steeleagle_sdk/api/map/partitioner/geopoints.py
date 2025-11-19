from __future__ import annotations
import math
from typing import Iterable, Tuple, List
from shapely.geometry import Polygon, LineString

class GeoPoints(list):
    """List[(x, y)] with helpers; (lon,lat) for WGS84 by convention."""

    def __init__(self, coords: Iterable[Tuple[float, float]] = ()):
        super().__init__((float(x), float(y)) for x, y in coords)

    def centroid(self) -> Tuple[float, float]:
        poly = self.to_polygon()
        c = poly.centroid
        return (c.x, c.y)

    def to_polygon(self) -> Polygon:
        if len(self) < 3:
            raise ValueError("A polygon must have at least 3 points")
        coords = list(self)
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return Polygon(coords)

    def to_linestring(self) -> LineString:
        if len(self) < 2:
            raise ValueError("A linestring must have at least 2 points")
        return LineString(self)

    # --- Simple local equirectangular projection around origin (lon0, lat0) ---
    @staticmethod
    def _project_to_meters(origin_wgs: Tuple[float, float], wgs: Tuple[float, float]) -> Tuple[float, float]:
        lon0, lat0 = origin_wgs
        lon, lat = wgs
        lat_rad = math.radians(lat0)
        x = (lon - lon0) * 111_320.0 * math.cos(lat_rad)
        y = (lat - lat0) * 110_540.0
        return (x, y)

    @staticmethod
    def _inverse_project(origin_wgs: Tuple[float, float], xy: Tuple[float, float]) -> Tuple[float, float]:
        lon0, lat0 = origin_wgs
        x, y = xy
        lat_rad = math.radians(lat0)
        lon = x / (111_320.0 * math.cos(lat_rad)) + lon0
        lat = y / 110_540.0 + lat0
        return (lon, lat)

    def convert_to_projected(self) -> GeoPoints:
        origin = self.centroid()
        return GeoPoints([self._project_to_meters(origin, p) for p in self])

    def inverse_project_from(self, origin_wgs: Tuple[float, float]) -> GeoPoints:
        return GeoPoints([self._inverse_project(origin_wgs, p) for p in self])
