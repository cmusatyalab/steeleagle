import asyncio
import math
from typing import Any, Dict, List, Literal, Optional
from pydantic import Field
# API imports
from ....compiler.registry import register_event
from ...base import Event

from .....dsl import runtime

''' General events '''
@register_event
class TimeReached(Event):
    duration: float = Field(..., ge=0.0, description="Seconds to wait before event triggers")

    async def check(self):
        """Wait for a fixed duration; return True once reached."""
        await asyncio.sleep(self.duration)
        return True
    
''' Telemetry events and helpers '''
def _get(t: Dict[str, Any], *path, default=None):
    cur = t
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

@register_event
class BatteryReached(Event):
    '''
    Fires when battery percentage satisfies relation to threshold for N consecutive polls.
    relation: `at_least` (greater than or equal to threshold) or `at_most` (less than or
    equal to threshold).
    '''
    threshold: int = Field(..., ge=0, le=100)
    relation: Literal["at_least", "at_most"] = "at_most"
    consecutive: int = Field(1, ge=1)
    _streak: int = 0  # internal

    async def check(self) -> bool:
        tel = await runtime.VEHICLE.get_telemetry()
        bat = _get(tel, "battery")
        if not isinstance(bat, (int, float)):
            self._streak = 0
            return False
        ok = (bat >= self.threshold) if self.relation == "at_least" else (bat <= self.threshold)
        self._streak = (self._streak + 1) if ok else 0
        return self._streak >= self.consecutive


@register_event
class SatellitesReached(Event):
    """
    Fires when satellites count satisfies relation to threshold for N consecutive polls.

    Attributes:
        relation: `at_least` (greater than or equal to) or `at_most` (less than or equal to).
    """
    threshold: int = Field(..., ge=0)
    relation: Literal["at_least", "at_most"] = "at_least"
    consecutive: int = Field(1, ge=1)
    _streak: int = 0

    async def check(self) -> bool:
        tel = await runtime.VEHICLE.get_telemetry()
        sats = _get(tel, "satellites")
        if not isinstance(sats, (int, float)):
            self._streak = 0
            return False
        ok = (sats >= self.threshold) if self.relation == "at_least" else (sats <= self.threshold)
        self._streak = (self._streak + 1) if ok else 0
        return self._streak >= self.consecutive


@register_event
class GimbalPoseReached(Event):
    """
    Fires when gimbal pose matches target within tolerances.
    You can specify any subset of `{roll, pitch, yaw}` (or x,y,z if your pose encodes axes).
    """
    # target angles/axes (degrees or units your telemetry uses)
    roll: Optional[float] = None
    pitch: Optional[float] = None
    yaw: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None

    # tolerances for each (defaults used when specific *_tol is None)
    tolerance: float = Field(1.0, ge=0.0)
    roll_tol: Optional[float] = None
    pitch_tol: Optional[float] = None
    yaw_tol: Optional[float] = None
    x_tol: Optional[float] = None
    y_tol: Optional[float] = None
    z_tol: Optional[float] = None

    def _within(self, cur: Optional[float], tgt: Optional[float], tol: Optional[float]) -> bool:
        if tgt is None:
            return True
        if cur is None:
            return False
        t = tol if tol is not None else self.tolerance
        return abs(cur - tgt) <= t

    async def check(self) -> bool:
        tel = await runtime.VEHICLE.get_telemetry()
        pose = _get('pose', tel)
        return (
            self._within(pose["roll"], self.roll, self.roll_tol) and
            self._within(pose["pitch"], self.pitch, self.pitch_tol) and
            self._within(pose["yaw"], self.yaw, self.yaw_tol) and
            self._within(pose["x"], self.x, self.x_tol) and
            self._within(pose["y"], self.y, self.y_tol) and
            self._within(pose["z"], self.z, self.z_tol)
        )


@register_event
class VelocityReached(Event):
    """
    Fires when speed magnitude in selected frame satisfies relation to threshold.

    Attributes:
        frame: `enu` or `body`
        relation: `at_least` or `at_most`
    """
    frame: Literal["enu", "body"] = "enu"
    threshold: float = Field(..., gt=0.0)
    relation: Literal["at_least", "at_most"] = "at_least"

    async def check(self) -> bool:
        tel = await runtime.VEHICLE.get_telemetry()
        pass


@register_event
class HomeReached(Event):
    """
    Fires when distance from current `global_position` to home less than or equal to `radius_m` (meters).
    Requires `global_position.{latitude, longitude}` and `home.{latitude, longitude}`.
    """
    radius_m: float = Field(..., gt=0.0)

    async def check(self) -> bool:
        tel = await runtime.VEHICLE.get_telemetry()
        pass


# ---------------- Compute events ----------------
# ---------------- events ----------------
@register_event
class DetectionFound(Event):
    """
    Fires when any detection matches optional filters:
      - `class_name` (case-insensitive) if provided
      - `min_score` greater than of equal to threshold if provided
    """
    compute_type: str = Field(..., min_length=1)
    target: Optional[str] = Field(None)
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    async def check(self) -> bool:
        pass


@register_event
class HSVReached(Event):
    """
    Fires when any detection indicates HSV filter passed (boolean flag).
    Optional filters: `class_name`, `min_score`.
    Assumes detection dicts may have `hsv_filter_passed`: bool.
    """
    compute_type: str = Field(..., min_length=1)
    class_name: Optional[str] = Field(None)
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    async def check(self) -> bool:
        pass