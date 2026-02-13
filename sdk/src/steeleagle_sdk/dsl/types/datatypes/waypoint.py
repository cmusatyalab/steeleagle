import logging
from typing import Literal

from pydantic import Field

from ....api.datatypes.common import Location
from ....api.map.partitioner.algos.corridor import CorridorPartition
from ....api.map.partitioner.algos.edge import EdgePartition
from ....api.map.partitioner.algos.survey import SurveyPartition
from ....api.map.partitioner.geopoints import GeoPoints
from ....api.map.partitioner.utils import parse_kml_file
from ...compiler.registry import register_data
from ..base import Datatype

logger = logging.getLogger(__name__)

from .. import MAP


class RelativeWaypoints(Datatype):
    pass


@register_data
class Waypoints(Datatype):
    """A list of geolocation waypoints with a slicing algorithm for coverage patterns."""

    area: str | list[Location] = Field(description="KML area name (string) or list of Location points defining the area.")
    alt: float = Field(description="Altitude at which waypoints are visited [meters]. Altitudes in Location objects are ignored.")
    algo: Literal["edge", "corridor", "survey"] | None = Field(default="edge", description="Slicing algorithm: 'edge' follows points in order, 'survey'/'corridor' cover the enclosed area.")
    spacing: float | None = Field(default=None, description="Spacing between survey/corridor columns [meters]. Required for survey/corridor.")
    angle_degrees: float | None = Field(default=None, description="Angle of survey/corridor columns [degrees]. Required for survey/corridor.")
    trigger_distance: float | None = Field(default=None, description="Distance before snapshot trigger [meters]. Required for survey only.")

    def calculate(self) -> dict[str, list[dict[str, float]]]:
        raw = None  # Raw geopoints

        # Check to see if a KML map has been sent or if Locations have been provided
        if MAP is None and isinstance(self.area, str):
            raise ValueError(
                "MAP is not set. Set map_mod.MAP to a fastkml.kml.KML before calling calculate()."
            )
        elif MAP:
            raw_map: dict[str, GeoPoints] = parse_kml_file(MAP)
            if not raw_map:
                logger.warning("No valid areas found in mission map (KML).")
                return {}

            if self.area not in raw_map:
                available = ", ".join(sorted(raw_map.keys()))
                raise ValueError(
                    f"Area '{self.area}' not found in mission map. Available areas: {available}"
                )

            raw = raw_map[self.area]
            if len(raw) < 3:
                logger.warning("Area %s has < 3 points; skipping.", self.area)
                return {}
        else:
            raw = GeoPoints([(p.latitude, p.longitude) for p in self.area])

        # Choose partitioner
        if self.algo == "edge":
            partition = EdgePartition()
        elif self.algo == "survey":
            if (
                self.spacing is None
                or self.angle_degrees is None
                or self.trigger_distance is None
            ):
                raise ValueError(
                    "For 'survey' algo, 'spacing', 'angle_degrees', and 'trigger_distance' must be set."
                )
            partition = SurveyPartition(
                spacing=self.spacing,
                angle_degrees=self.angle_degrees,
                trigger_distance=self.trigger_distance,
            )
        elif self.algo == "corridor":
            if self.spacing is None or self.angle_degrees is None:
                raise ValueError(
                    "For 'corridor' algo, 'spacing' and 'angle_degrees' must be set."
                )
            partition = CorridorPartition(
                spacing=self.spacing,
                angle_degrees=self.angle_degrees,
            )
        else:
            msg = f"Unknown algo '{self.algo}'. Expected one of: 'edge', 'survey', 'corridor'."
            raise ValueError(msg)

        origin_wgs = raw.centroid()
        projected = raw.convert_to_projected()
        poly = projected.to_polygon()

        parts_m = partition.generate_partitioned_geopoints(poly)
        parts_wgs = [GeoPoints(p).inverse_project_from(origin_wgs) for p in parts_m]

        # Flatten segments to per-point waypoints
        waypoints: list[dict[str, float]] = []
        for gp in parts_wgs:
            for lon, lat in gp:
                waypoints.append(
                    {"lat": float(lat), "lon": float(lon), "alt": float(self.alt)}
                )

        logger.info(
            "Partitioned '%s' with %s: %d segment(s), %d point(s)",
            self.area,
            self.algo,
            len(parts_wgs),
            len(waypoints),
        )
        key = self.area if isinstance(self.area, str) else "inline_area"
        return {key: waypoints}