from pathlib import Path
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from ...dsl.compiler.registry import register_data
from ...dsl.partitioner.algos.corridor import CorridorPartition
from ...dsl.partitioner.algos.edge import EdgePartition
from ...dsl.partitioner.algos.survey import SurveyPartition

from ...dsl.partitioner.geopoints import GeoPoints
from ...dsl.partitioner.utils import parse_kml_file
import logging
logger = logging.getLogger(__name__)



class RelativePoint(BaseModel):
    pass  # Placeholder for future implementation


@register_data
# Collection of waypoints
class Waypoints(BaseModel):
    alt: float
    path: str
    algo: Literal["edge", "survey", "corridor"]
    spacing: float
    angle_degrees: float
    trigger_distance: float

    def calculate(self) -> Dict[str, List[Dict[str, float]]]:
        """
        Partition areas from a KML/GeoJSON and return:
        { area_name: [ {lat: float, long: float, alt: float}, ... ] }
        """
        if not self.path:
            raise ValueError("Waypoints.path is required")

        path = Path(self.path)
        if not path.exists():
            raise FileNotFoundError(f"KML file not found: {path}")

        raw_map = parse_kml_file(str(path))
        if not raw_map:
            logger.warning("No valid areas found in KML file: %s", path)
            return {}

        # Pick partitioner
        if self.algo == "edge":
            partition = EdgePartition()
        elif self.algo == "survey":
            partition = SurveyPartition(
                spacing=self.spacing,
                angle_degrees=self.angle_degrees,
                trigger_distance=self.trigger_distance,
            )
        elif self.algo == "corridor":
            partition = CorridorPartition(
                spacing=self.spacing,
                angle_degrees=self.angle_degrees,
            )
        else:
            raise ValueError(f"Unknown algo '{self.algo}'. Expected one of: 'edge', 'survey', 'corridor'.")

        result: Dict[str, List[Dict[str, float]]] = {}

        for area, raw in raw_map.items():
            if len(raw) < 3:
                logger.warning("Area %s has < 3 points; skipping.", area)
                continue
            
            # Project to meters, partition, inverse-project back to WGS84
            origin_wgs = raw.centroid()
            projected = raw.convert_to_projected()
            poly = projected.to_polygon()
            parts_m = partition.generate_partitioned_geopoints(poly)
            parts_wgs = [GeoPoints(p).inverse_project_from(origin_wgs) for p in parts_m]

            # Flatten segments
            waypoints: List[Dict[str, float]] = []
            for wg in parts_wgs:
                lng, lat = wg
                waypoints.append({"lat": float(lat), "lng": float(lng), "alt": float(self.alt)})
            result[area] = waypoints
            logger.info(
                "Partitioned '%s': %d segment(s), %d point(s)",
                area,
                len(parts_wgs),
                len(waypoints),
            )

        return result
