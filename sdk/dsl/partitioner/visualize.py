from __future__ import annotations
from typing import List, Tuple
from shapely.geometry import Polygon
from .geopoints import GeoPoints

def visualize(polygons: List[Polygon], paths: List[List[Tuple[float, float]]]) -> None:
    """
    Draw polygons + waypoint polylines/points using matplotlib.
    (Coordinates should be in the same CRS; for nice aspect use projected meters.)
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect('equal', adjustable='box')

    for poly in polygons:
        xs, ys = poly.exterior.xy
        ax.plot(xs, ys, linewidth=1.5)

    for coords in paths:
        if len(coords) >= 2:
            xs = [p[0] for p in coords]
            ys = [p[1] for p in coords]
            ax.plot(xs, ys, linewidth=1.2)
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        ax.scatter(xs, ys, s=10)

    ax.set_title("Partition Visualizer")
    ax.grid(True, linestyle=":")
    plt.show()
