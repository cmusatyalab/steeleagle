from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

# One waypoint point (lat/lon/alt)
class GeoPoint(BaseModel):
    lat: float
    lon: float
    alt: float = 0.0

class RelativePoint(BaseModel):
    pass  # Placeholder for future implementation

# Collection of waypoints
class Waypoints(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None    # path to KML/GeoJSON file
    algo: Optional[Literal["edge", "survey", "corridor"]] = None
    points: Optional[List[GeoPoint]] = None  # inline (lat,lon,alt) list

    @model_validator(mode="after")   # runs after the model is created
    def _one_of(self):
        has_file = self.path is not None
        has_points = self.points is not None and len(self.points) > 0
        if has_file ^ has_points:   # XOR: true if exactly one is set
            return self
        raise ValueError("Waypoints: set either (path+algo) OR points[...]")