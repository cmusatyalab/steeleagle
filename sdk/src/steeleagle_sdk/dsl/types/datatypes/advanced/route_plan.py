from __future__ import annotations

from typing import Literal

from pydantic import Field

from ....compiler.registry import register_data
from ...base import Datatype
from ..primitives.common import Location
from ..primitives.map import Map


class RelativeWaypoints(Datatype):
    pass


@register_data
class RoutePlan(Datatype):
    """Configuration for partitioning a mission-map area into flight waypoints."""

    area: str = Field(description="Name of an area in `map` (or the mission map, if unset).")
    alt: float = Field(
        description="Altitude at which waypoints are visited [meters]."
    )
    algo: Literal["edge", "corridor", "survey"] = Field(
        default="edge",
        description="Slicing algorithm: 'edge' follows boundary points in order, 'survey'/'corridor' cover the enclosed area.",
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

    def apply(self, map: Map) -> list[Location]:
        return map.navigate(
            area=self.area,
            algo=self.algo,
            spacing=self.spacing,
            angle_degrees=self.angle_degrees,
            trigger_distance=self.trigger_distance,
        )
