import asyncio
import math
from typing import Any, Dict, List, Literal, Optional
from pydantic import Field
# API imports
from ...dsl.compiler.registry import register_event
from ..base import Event

''' General events '''
@register_event
class TimeReached(Event):
    duration: float = Field(..., ge=0.0, description="Seconds to wait before event triggers")

    async def check(self, context):
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

def _relative_altitude(tel: Dict[str, Any]) -> Optional[float]:
    ra = _get(tel, "global_position", "relative_altitude")
    if isinstance(ra, (int, float)):
        return float(ra)
    z = _get(tel, "relative_position", "z")
    if isinstance(z, (int, float)):
        return float(z)
    alt = _get(tel, "global_position", "altitude")
    if isinstance(alt, (int, float)):
        return float(alt)
    return None

def _pose_components(tel: Dict[str, Any]) -> Dict[str, Optional[float]]:
    pose = _get(tel, "gimbal_pose") or {}
    out = {"roll": None, "pitch": None, "yaw": None, "x": None, "y": None, "z": None}
    for k in out.keys():
        v = pose.get(k)
        if isinstance(v, (int, float)):
            out[k] = float(v)
    return out

def _speed_mag(tel: Dict[str, Any], frame: Literal["enu", "body"]) -> Optional[float]:
    node = "velocity_enu" if frame == "enu" else "velocity_body"
    vx = _get(tel, node, "x")
    vy = _get(tel, node, "y")
    vz = _get(tel, node, "z")
    if all(isinstance(v, (int, float)) for v in (vx, vy, vz)):
        return float(math.sqrt(v * v + vy * vy + vz * vz))
    return None

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

@register_event
class BatteryReached(Event):
    '''
    Fires when battery % satisfies relation to threshold for N consecutive polls.
    relation: 'at_least' (>= threshold) or 'at_most' (<= threshold)
    '''
    threshold: int = Field(..., ge=0, le=100)
    relation: Literal["at_least", "at_most"] = "at_most"
    consecutive: int = Field(1, ge=1)
    _streak: int = 0  # internal

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
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
    relation: 'at_least' (>=) or 'at_most' (<=)
    """
    threshold: int = Field(..., ge=0)
    relation: Literal["at_least", "at_most"] = "at_least"
    consecutive: int = Field(1, ge=1)
    _streak: int = 0

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
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

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        pose = _pose_components(tel)
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
    frame: 'enu' or 'body'
    relation: 'at_least' (>=) or 'at_most' (<=)
    """
    frame: Literal["enu", "body"] = "enu"
    threshold: float = Field(..., gt=0.0)
    relation: Literal["at_least", "at_most"] = "at_least"

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        spd = _speed_mag(tel, self.frame)
        if spd is None:
            return False
        return spd >= self.threshold if self.relation == "at_least" else spd <= self.threshold


@register_event
class HomeReached(Event):
    """
    Fires when distance from current global_position to home <= radius_m (meters).
    Requires global_position.{latitude, longitude} and home.{latitude, longitude}.
    """
    radius_m: float = Field(..., gt=0.0)

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        lat = _get(tel, "global_position", "latitude")
        lon = _get(tel, "global_position", "longitude")
        hlat = _get(tel, "home", "latitude")
        hlon = _get(tel, "home", "longitude")
        if not all(isinstance(v, (int, float)) for v in (lat, lon, hlat, hlon)):
            return False
        d = _haversine_m(float(lat), float(lon), float(hlat), float(hlon))
        return d <= self.radius_m
    


# ---------------- Compute events ----------------
# ---------------- helpers ----------------

def _extract_detections(results: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Normalizes various shapes to a flat list of detection dicts.
    Supports:
      - {'detection_result': {'detections': [ ... ]}}
      - {'detections': [ ... ]}
      - direct detection dicts (best-effort)
    """
    out: List[Dict[str, Any]] = []
    if not results:
        return out
    for r in results:
        if not isinstance(r, dict):
            continue
        if "detection_result" in r and isinstance(r["detection_result"], dict):
            dets = r["detection_result"].get("detections", [])
            if isinstance(dets, list):
                out.extend(d for d in dets if isinstance(d, dict))
            continue
        if "detections" in r and isinstance(r["detections"], list):
            out.extend(d for d in r["detections"] if isinstance(d, dict))
            continue
        # best-effort: if it looks like a detection on its own
        if "score" in r or "class_name" in r or "bbox" in r:
            out.append(r)
    return out

# ---------------- events ----------------
@register_event
class DetectionFound(Event):
    """
    Fires when any detection matches optional filters:
      - class_name (case-insensitive) if provided
      - min_score >= threshold if provided
    """
    compute_type: str = Field(..., min_length=1)
    target: Optional[str] = Field(None)
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    async def check(self, context) -> bool:
        results = await context["data"].get_compute_result(self.compute_type)
        dets = _extract_detections(results)
        if not dets:
            return False

        want_class = self.class_name.lower() if isinstance(self.class_name, str) else None
        for d in dets:
            cls = d.get("class_name")
            scr = d.get("score")
            if want_class is not None and (not isinstance(cls, str) or cls.lower() != want_class):
                continue
            if self.min_score is not None:
                try:
                    if float(scr) < float(self.min_score):
                        continue
                except Exception:
                    continue
            return True
        return False


@register_event
class HSVReached(Event):
    """
    Fires when any detection indicates HSV filter passed (boolean flag).
    Optional filters: class_name, min_score.
    Assumes detection dicts may have 'hsv_filter_passed': bool.
    """
    compute_type: str = Field(..., min_length=1)
    class_name: Optional[str] = Field(None)
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    async def check(self, context) -> bool:
        results = await context["data"].get_compute_result(self.compute_type)
        dets = _extract_detections(results)
        if not dets:
            return False

        want_class = self.class_name.lower() if isinstance(self.class_name, str) else None
        for d in dets:
            if not d.get("hsv_filter_passed", False):
                continue
            cls = d.get("class_name")
            scr = d.get("score")
            if want_class is not None and (not isinstance(cls, str) or cls.lower() != want_class):
                continue
            if self.min_score is not None:
                try:
                    if float(scr) < float(self.min_score):
                        continue
                except Exception:
                    continue
            return True
        return False
