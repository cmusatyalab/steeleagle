from __future__ import annotations
from .... import types
from .common import Area, Location
from .....api.datatypes.common import Area as ApiArea
from .....api.datatypes.map import Map as ApiMap
# This class is only for dsl type developers and is not exposed to the compiler.

class Map():
    """A named collection of `Area`s: the DSL-facing view of a mission map."""

    map: ApiMap
    _is_mission_map: bool = False

    def __init__(self, area: Area | None = None):
        if area is None:
            if types.MAP is None:
                raise ValueError("Cannot create Map based on mission map when mission map is not set")
            self.map = types.MAP
            self._is_mission_map = True
        else:
            self.map = ApiMap(areas={area.name: ApiArea.model_validate(area, from_attributes=True)})

    @classmethod
    def _wrap(cls, api_map: ApiMap) -> Map:
        """Wrap an already-built `ApiMap` without going through `__init__`."""
        obj = cls.__new__(cls)
        obj.map = api_map
        obj._is_mission_map = False
        return obj

    def get_area(self, name: str) -> Area:
        return Area.model_validate(self.map.get_area(name), from_attributes=True)

    def add_area(self, area: Area) -> None:
        if self._is_mission_map:
            raise ValueError("Cannot add area to mission map")
        self.map.add_area(ApiArea.model_validate(area, from_attributes=True))

    def get_all_areas(self) -> list[Area]:
        return [Area.model_validate(area, from_attributes=True) for area in self.map.get_all_areas()]

    def merge(self, other: Map) -> Map:
        # make a new map that merges the two maps together
        current_areas = self.map.get_all_areas()
        other_areas = other.map.get_all_areas()
        merged_areas = {area.name: area for area in current_areas + other_areas}
        return Map._wrap(ApiMap(areas=merged_areas))

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
