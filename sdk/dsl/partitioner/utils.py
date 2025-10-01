from __future__ import annotations
import math
from shapely.geometry import Point, LineString, Polygon
from shapely.affinity import rotate
from typing import Dict, Tuple, List
from xml.dom import minidom
from .geopoints import GeoPoints

def round_xy(x: float, y: float, decimals: int = 3) -> Tuple[float, float]:
    k = 10 ** decimals
    return (round(x * k) / k, round(y * k) / k)

def line_polygon_intersection_points(line: LineString, polygon: Polygon) -> List[Tuple[float, float]]:
    inter = line.intersection(polygon.boundary)
    pts: List[Tuple[float, float]] = []

    def add_pt(p: Point):
        pts.append((p.x, p.y))

    if inter.is_empty:
        return []

    if isinstance(inter, Point):
        add_pt(inter)
    else:
        for geom in getattr(inter, "geoms", [inter]):
            if isinstance(geom, Point):
                add_pt(geom)
            elif isinstance(geom, LineString):
                c = list(geom.coords)
                add_pt(Point(c[0]))
                add_pt(Point(c[-1]))

    # Dedup (rounded) & sort along line parameter
    seen = set()
    out: List[Tuple[float, float]] = []
    for x, y in pts:
        rx, ry = round_xy(x, y, 6)
        if (rx, ry) not in seen:
            seen.add((rx, ry))
            out.append((x, y))

    p0 = line.coords[0]
    p1 = line.coords[-1]
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    denom = dx * dx + dy * dy or 1.0

    def tparam(pt: Tuple[float, float]) -> float:
        x, y = pt
        return ((x - p0[0]) * dx + (y - p0[1]) * dy) / denom

    out.sort(key=tparam)
    return out

def rotated_infinite_transects(polygon: Polygon, spacing: float, angle_deg: float) -> List[LineString]:
    minx, miny, maxx, maxy = polygon.envelope.bounds
    width = maxx - minx
    height = maxy - miny
    max_len = max(width, height) + 100.0
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0

    lines: List[LineString] = []
    x = minx - max_len
    end_x = maxx + max_len

    verticals: List[LineString] = []
    while x <= end_x:
        verticals.append(LineString([(x, miny - max_len), (x, maxy + max_len)]))
        x += spacing

    return [rotate(v, angle_deg, origin=(cx, cy), use_radians=False) for v in verticals]



def parse_kml_file(kml_path: str) -> Dict[str, GeoPoints]:
    """
    Parse KML Placemarks with <coordinates> entries "lon,lat[,alt]".
    Returns `{placemark_name: GeoPoints([(lon,lat), ...])}`
    """
    doc = minidom.parse(kml_path)
    placemarks = doc.getElementsByTagName("Placemark")
    result: Dict[str, GeoPoints] = {}

    for pm in placemarks:
        name_nodes = pm.getElementsByTagName("name")
        coords_nodes = pm.getElementsByTagName("coordinates")
        if not name_nodes or not coords_nodes:
            continue
        name = name_nodes[0].firstChild.nodeValue.strip()
        coords_text = coords_nodes[0].firstChild.nodeValue.strip()
        gp = parse_kml_coordinates_to_geopoints(coords_text)
        result[name] = gp
    return result


def parse_kml_coordinates_to_geopoints(kml_coordinates: str) -> GeoPoints:
    pts: List[Tuple[float, float]] = []
    for token in kml_coordinates.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            lon = float(parts[0])
            lat = float(parts[1])
            pts.append((lon, lat))
    return GeoPoints(pts)
