from __future__ import annotations
from .... import types
from .common import Area, Location
from .....api.datatypes.common import Area as ApiArea
from .....api.datatypes.map import Map as ApiMap
# This class is only for dsl type developers and is not exposed to the compiler.

class Map():
    """A named collection of `Area`s: the DSL-facing view of a mission map."""

    map: ApiMap

    def __init__(self, area: Area | None = None):
        if area is None:
            if types.MAP is None:
                raise ValueError("Cannot create Map based on mission map when mission map is not set")
            self.map = ApiMap(areas=dict(types.MAP.areas))
        else:
            self.map = ApiMap(areas={area.name: ApiArea.model_validate(area, from_attributes=True)})

    def get_area(self, name: str) -> Area:
        return Area.model_validate(self.map.get_area(name), from_attributes=True)

    def add_area(self, area: Area) -> None:
        self.map.add_area(ApiArea.model_validate(area, from_attributes=True))

    def update(self, area: Area) -> None:
        self.map.update_area(ApiArea.model_validate(area, from_attributes=True))

    def get_all_areas(self) -> list[Area]:
        return [Area.model_validate(area, from_attributes=True) for area in self.map.get_all_areas()]

    def merge(self, other: Map) -> None:
        for area in other.map.get_all_areas():
            self.map.update_area(area)

    def navigate(
        self,
        area: str,
        algo: str,
        spacing: float | None = None,
        angle_degrees: float | None = None,
        trigger_distance: float | None = None,
    ) -> list[Location]:
        raw_locations = self.map.navigate(
            area_name=area,
            algo=algo,
            spacing=spacing,
            angle_degrees=angle_degrees,
            trigger_distance=trigger_distance,
        )
        return [Location.model_validate(loc, from_attributes=True) for loc in raw_locations]
