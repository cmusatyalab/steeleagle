from __future__ import annotations

from typing import Literal

from .._base import Datatype
from ..common import Area, Location
from .partitioner.algos.corridor import CorridorPartition
from .partitioner.algos.edge import EdgePartition
from .partitioner.algos.survey import SurveyPartition
from .partitioner.utils import centroid, inverse_project, parse_kml_file, project_to_meters, to_polygon


class Map(Datatype):
    """A named collection of `Area`s (see `datatypes.common.Area`), loadable from KML."""

    areas: dict[str, Area] = {}

    @classmethod
    def from_kml(cls, kml: str) -> Map:
        """Parse a KML document's Placemarks into named `Area`s."""
        return cls(areas=parse_kml_file(kml))

    def get_area(self, name: str) -> Area:
        if name not in self.areas:
            available = ", ".join(sorted(self.areas.keys()))
            raise ValueError(f"Area '{name}' not found in map. Available areas: {available}")
        return self.areas[name]

    def add_area(self, area: Area) -> None:
        if not area.name:
            raise ValueError("Cannot add an unnamed area to a map")
        self.areas[area.name] = area

    def update_area(self, area: Area) -> None:
        if not area.name:
            raise ValueError("Cannot update with an unnamed area")
        self.areas[area.name] = area

    def get_all_areas(self) -> list[Area]:
        return list(self.areas.values())

    def merge(self, other: Map) -> Map:
        """Return a new `Map` with `other`'s areas layered on top of this one's."""
        return Map(areas={**self.areas, **other.areas})

    def navigate(
        self,
        area_name: str,
        algo: Literal["edge", "corridor", "survey"] = "edge",
        spacing: float | None = None,
        angle_degrees: float | None = None,
        trigger_distance: float | None = None,
    ) -> list[Location]:
        """Partition a named area's boundary and return the resulting GPS waypoints."""
        return Map.calculate_area(
            self.get_area(area_name),
            algo=algo,
            spacing=spacing,
            angle_degrees=angle_degrees,
            trigger_distance=trigger_distance,
        )

    @staticmethod
    def calculate_area(
        area: Area,
        algo: Literal["edge", "corridor", "survey"] = "edge",
        spacing: float | None = None,
        angle_degrees: float | None = None,
        trigger_distance: float | None = None,
    ) -> list[Location]:
        """Partition an area's boundary and return the resulting GPS waypoints."""
        if algo == "edge":
            partition = EdgePartition()
        elif algo == "survey":
            missing = [
                n
                for n, v in (
                    ("spacing", spacing),
                    ("angle_degrees", angle_degrees),
                    ("trigger_distance", trigger_distance),
                )
                if v is None
            ]
            if missing:
                raise ValueError(
                    f"For 'survey' algo, the following parameters are required: {', '.join(missing)}"
                )
            partition = SurveyPartition(
                spacing=spacing,
                angle_degrees=angle_degrees,
                trigger_distance=trigger_distance,
            )
        elif algo == "corridor":
            missing = [
                n for n, v in (("spacing", spacing), ("angle_degrees", angle_degrees)) if v is None
            ]
            if missing:
                raise ValueError(
                    f"For 'corridor' algo, the following parameters are required: {', '.join(missing)}"
                )
            partition = CorridorPartition(spacing=spacing, angle_degrees=angle_degrees)
        else:
            raise ValueError(
                f"Unknown algo '{algo}'. Expected one of: 'edge', 'survey', 'corridor'."
            )

        coords = [(p.longitude, p.latitude) for p in area.points]
        origin = centroid(coords)
        poly = to_polygon(project_to_meters(coords, origin))

        locations: list[Location] = []
        for segment in partition.generate_partitioned_geopoints(poly):
            for xy in segment:
                lon, lat = inverse_project(xy, origin)
                locations.append(Location(latitude=lat, longitude=lon))
        return locations
