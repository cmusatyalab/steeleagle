import logging
from typing import Literal

from pydantic import Field, model_validator

from ....api.datatypes.common import Location
from ....api.map.partitioner.algos.corridor import CorridorPartition
from ....api.map.partitioner.algos.edge import EdgePartition
from ....api.map.partitioner.algos.survey import SurveyPartition
from ....api.map.partitioner.geopoints import GeoPoints
from ....api.map.partitioner.utils import parse_kml_file
from ... import types
from ...compiler.registry import register_data
from ..base import Datatype

logger = logging.getLogger(__name__)


class RelativeWaypoints(Datatype):
    pass


@register_data
class Waypoints(Datatype):
    """A list of geolocation waypoints with a slicing algorithm for coverage patterns."""

    area: str | list[Location] | None = Field(
        default=None,
        description="KML area name (string) or list of Location points defining the area. If omitted, every area in the KML is used.",
    )
    kml: str | None = Field(
        default=None,
        description="KML document to slice, overriding the mission map. Use for KMLs received at runtime (e.g. a navigation result).",
    )
    alt: float = Field(
        description="Altitude at which waypoints are visited [meters]. Altitudes in Location objects are ignored."
    )
    algo: Literal["edge", "corridor", "survey"] | None = Field(
        default="edge",
        description="Slicing algorithm: 'edge' follows points in order, 'survey'/'corridor' cover the enclosed area.",
    )
    spacing: float | None = Field(
        default=None,
        description="Spacing between survey/corridor columns [meters]. Required for survey/corridor.",
    )
    angle_degrees: float | None = Field(
        default=None,
        description="Angle of survey/corridor columns [degrees]. Required for survey/corridor.",
    )
    trigger_distance: float | None = Field(
        default=None,
        description="Distance before snapshot trigger [meters]. Required for survey only.",
    )

    @model_validator(mode="after")
    def validate_algo_requirements(self):
        """Validate that required parameters are present based on the selected algorithm."""
        if self.algo == "survey":
            missing = []
            if self.spacing is None:
                missing.append("spacing")
            if self.angle_degrees is None:
                missing.append("angle_degrees")
            if self.trigger_distance is None:
                missing.append("trigger_distance")
            if missing:
                raise ValueError(
                    f"For 'survey' algo, the following parameters are required: {', '.join(missing)}"
                )
        elif self.algo == "corridor":
            missing = []
            if self.spacing is None:
                missing.append("spacing")
            if self.angle_degrees is None:
                missing.append("angle_degrees")
            if missing:
                raise ValueError(
                    f"For 'corridor' algo, the following parameters are required: {', '.join(missing)}"
                )
        return self

    def _resolve_areas(self, kml: str | None = None) -> dict[str, GeoPoints]:
        """Resolve the target area(s) to raw geopoints.

        KML source precedence: the `kml` argument, then the `kml` field, then the
        mission map (`types.MAP`). Inline Location lists bypass KML entirely.
        """
        # Check to see if Locations have been provided instead of a KML area
        if isinstance(self.area, list):
            return {
                "inline_area": GeoPoints(
                    [(p.longitude, p.latitude) for p in self.area]
                )
            }

        source = kml or self.kml or types.MAP
        if source is None:
            raise ValueError(
                "No KML available. Pass calculate(kml=...), set the 'kml' field, "
                "or set types.MAP to a KML string before calling calculate()."
            )

        raw_map: dict[str, GeoPoints] = parse_kml_file(source)
        if not raw_map:
            logger.warning("No valid areas found in KML.")
            return {}

        # No area named: slice every placemark in the document. Runtime KMLs
        # (e.g. navigation results) use names the mission did not choose.
        if self.area is None:
            return raw_map

        if self.area not in raw_map:
            available = ", ".join(sorted(raw_map.keys()))
            raise ValueError(
                f"Area '{self.area}' not found in KML. Available areas: {available}"
            )
        return {self.area: raw_map[self.area]}

    def _make_partition(self):
        """Choose partitioner (validation already done by @model_validator)."""
        if self.algo == "edge":
            return EdgePartition()
        elif self.algo == "survey":
            return SurveyPartition(
                spacing=self.spacing,
                angle_degrees=self.angle_degrees,
                trigger_distance=self.trigger_distance,
            )
        elif self.algo == "corridor":
            return CorridorPartition(
                spacing=self.spacing,
                angle_degrees=self.angle_degrees,
            )
        else:
            # This should never happen due to Literal type, but keep for safety
            msg = f"Unknown algo '{self.algo}'. Expected one of: 'edge', 'survey', 'corridor'."
            raise ValueError(msg)

    def calculate(self, kml: str | None = None) -> dict[str, list[dict[str, float]]]:
        areas = self._resolve_areas(kml)
        partition = self._make_partition()

        result: dict[str, list[dict[str, float]]] = {}
        for name, raw in areas.items():
            if len(raw) < 3:
                logger.warning("Area %s has < 3 points; skipping.", name)
                continue

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
                name,
                self.algo,
                len(parts_wgs),
                len(waypoints),
            )
            result[name] = waypoints

        return result
