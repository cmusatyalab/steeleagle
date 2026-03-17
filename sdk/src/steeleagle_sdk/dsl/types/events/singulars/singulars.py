import asyncio
import json
import logging
import math

from pydantic import Field

from ....compiler.registry import register_event
from ...base import Event
from ...datatypes.common import Location, Pose, Position, Velocity
from ...datatypes.result import BoundingBox, Detection, FrameResult
from ...datatypes.control import ReferenceFrame
from ...datatypes.result import HSV, Detection, FrameResult
from ...datatypes.telemetry import DriverTelemetry
from ...utils import fetch_results, fetch_telemetry

logger = logging.getLogger(__name__)


# ---- events ----
@register_event
class TimeReached(Event):
    """True after a specified duration has elapsed."""

    duration: float = Field(..., ge=0.0, description="Seconds to wait before returning true.")

    async def check(self) -> bool:
        await asyncio.sleep(self.duration)
        return True


@register_event
class BatteryReached(Event):
    """True when battery <= threshold."""

    threshold: int = Field(..., ge=0, le=100, description="Battery percentage [0-100] at or below which this event fires.")

    async def check(self) -> bool:
        while True:
            tel = await fetch_telemetry()
            if not tel or not tel.vehicle_info or not tel.vehicle_info.battery_info:
                continue
            pct = tel.vehicle_info.battery_info.percentage
            if pct is not None and pct <= self.threshold:
                return True


@register_event
class SatellitesReached(Event):
    """True when satellites >= threshold."""

    threshold: int = Field(..., ge=0, description="Minimum number of GPS satellites required for this event to fire.")

    async def check(self) -> bool:
        while True:
            tel = await fetch_telemetry()
            if not tel or not tel.vehicle_info or not tel.vehicle_info.gps_info:
                continue
            sats = tel.vehicle_info.gps_info.satellites
            if sats is not None and sats >= self.threshold:
                return True


@register_event
class GimbalPoseReached(Event):
    """Checks provided axes only; abs error <= tol_deg."""

    target: Pose = Field(description="Target gimbal pose (pitch, roll, yaw) [degrees]. Only provided axes are checked.")
    tol_deg: float = Field(3.0, gt=0.0, description="Allowed absolute error per axis [degrees].")

    async def check(self) -> bool:
        while True:
            tel = await fetch_telemetry()
            if not tel or not tel.gimbal_info or not tel.gimbal_info.gimbals:
                continue

            for g in tel.gimbal_info.gimbals or []:
                actual = g.pose_body or g.pose_neu
                if not actual:
                    continue

                ok = True
                if self.target.roll is not None and (
                    actual.roll is None
                    or abs(actual.roll - self.target.roll) > self.tol_deg
                ):
                    ok = False
                if self.target.pitch is not None and (
                    actual.pitch is None
                    or abs(actual.pitch - self.target.pitch) > self.tol_deg
                ):
                    ok = False
                if self.target.yaw is not None and (
                    actual.yaw is None
                    or abs(actual.yaw - self.target.yaw) > self.tol_deg
                ):
                    ok = False

                if ok:
                    return True


@register_event
class VelocityReached(Event):
    """True when the selected frame's velocity matches the target (per-component) within tolerance."""

    frame: ReferenceFrame = Field(description="Reference frame to check velocity in. Enum values: 0=BODY (vehicle frame), 1=NEU (North-East-Up).")
    target: Velocity = Field(description="Target velocity (x_vel, y_vel, z_vel, angular_vel). Only provided components are checked.")
    tol: float | None = Field(
        0, ge=0.0, description="Allowed absolute error per component [m/s]."
    )

    async def check(self) -> bool:
        while True:
            tel = await fetch_telemetry()
            if not tel or not tel.position_info:
                continue

            if self.frame == ReferenceFrame.BODY:
                v = tel.position_info.velocity_body
            elif self.frame == ReferenceFrame.NEU:
                v = tel.position_info.velocity_neu
            else:
                continue

            if v is None:
                continue

            if self.target.x_vel is not None and (
                v.x_vel is None or abs(v.x_vel - self.target.x_vel) > self.tol
            ):
                continue
            if self.target.y_vel is not None and (
                v.y_vel is None or abs(v.y_vel - self.target.y_vel) > self.tol
            ):
                continue
            if self.target.z_vel is not None and (
                v.z_vel is None or abs(v.z_vel - self.target.z_vel) > self.tol
            ):
                continue
            if self.target.angular_vel is not None and (
                v.angular_vel is None
                or abs(v.angular_vel - self.target.angular_vel) > self.tol
            ):
                continue

            return True


@register_event
class RelativePositionReached(Event):
    """
    True when the current relative_position matches the target within tolerance.
    Compares only fields provided on `target`.
    """

    target: Position = Field(description="Target relative position (x, y, z, angle). Only provided fields are checked.")
    tol_m: float | None = Field(
        0.20, ge=0.0, description="Tolerance for x/y/z [meters]."
    )
    tol_deg: float | None = Field(
        0.0, ge=0.0, description="Tolerance for angle [degrees]."
    )

    @staticmethod
    def _deg_diff(a: float, b: float) -> float:
        d = abs((a - b) % 360.0)
        return d if d <= 180.0 else 360.0 - d

    async def check(self) -> bool:
        while True:
            tel: DriverTelemetry | None = await fetch_telemetry()
            if not tel or not tel.position_info:
                continue
            cur = tel.position_info.relative_position
            if not cur:
                continue

            if self.target.x is not None and (
                cur.x is None or abs(cur.x - self.target.x) > self.tol_m
            ):
                continue
            if self.target.y is not None and (
                cur.y is None or abs(cur.y - self.target.y) > self.tol_m
            ):
                continue
            if self.target.z is not None and (
                cur.z is None or abs(cur.z - self.target.z) > self.tol_m
            ):
                continue
            if self.target.angle is not None and (
                cur.angle is None
                or self._deg_diff(cur.angle, self.target.angle) > self.tol_deg
            ):
                continue

            return True


@register_event
class GlobalPositionReached(Event):
    """
    True when the current global_position matches the target within tolerance.
    Uses great-circle distance for lat/lon, and optional checks for altitude and heading.
    Compares only fields provided on `target`.
    """

    target: Location = Field(default=None, description="Target global position (latitude, longitude, altitude, heading). Only provided fields are checked.")
    tol_m: float | None = Field(
        0.50, ge=0.0, description="Lat/lon great-circle distance tolerance [meters]."
    )
    tol_alt_m: float | None = Field(
        0.50, ge=0.0, description="Altitude tolerance [meters]."
    )
    tol_deg: float | None = Field(
        3.0, ge=0.0, description="Heading tolerance [degrees]."
    )

    @staticmethod
    def _haversine_m(a: Location | None, b: Location | None) -> float | None:
        if (
            not a
            or not b
            or a.latitude is None
            or a.longitude is None
            or b.latitude is None
            or b.longitude is None
        ):
            return None
        R = 6371000.0
        lat1, lon1, lat2, lon2 = map(
            math.radians, [a.latitude, a.longitude, b.latitude, b.longitude]
        )
        dlat, dlon = lat2 - lat1, lon2 - lon1
        h = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(h))

    @staticmethod
    def _deg_diff(a: float, b: float) -> float:
        d = abs((a - b) % 360.0)
        return d if d <= 180.0 else 360.0 - d

    async def check(self) -> bool:
        while True:
            if self.target is None:
                continue

            tel: DriverTelemetry | None = await fetch_telemetry()
            if not tel or not tel.position_info:
                continue
            cur = tel.position_info.global_position
            if not cur:
                continue

            # If latitude & longitude specified, require distance within tol_m
            if self.target.latitude is not None and self.target.longitude is not None:
                d = self._haversine_m(cur, self.target)
                if d is None or d > self.tol_m:
                    continue

            # Altitude (optional)
            if self.target.altitude is not None and (
                cur.altitude is None
                or abs(cur.altitude - self.target.altitude) > self.tol_alt_m
            ):
                continue

            # Heading (optional)
            if self.target.heading is not None and (
                cur.heading is None
                or self._deg_diff(cur.heading, self.target.heading) > self.tol_deg
            ):
                continue

            return True


# ---- compute events ----
@register_event
class DetectionFound(Event):
    """True if any detection matches optional class_name and min score."""

    target: Detection = Field(description="Detection filter (class_name to match, optional minimum score threshold).")

    async def check(self) -> bool:
        # Keep consuming FrameResult messages until a matching detection appears.
        while True:
            res: FrameResult = await fetch_results("object-engine")
            logger.debug("fetched results: %s", res)

            if not res or not res.result:
                continue  # no ComputeResult entries

            for compute in res.result:
                det_result = compute.detection_result
                if not det_result or not det_result.detections:
                    continue

                for det in det_result.detections:
                    if det is None:
                        continue
                    if self._matches_target(det):
                        return True

    def _matches_target(self, det: Detection) -> bool:
        # Filter on class_name if provided
        if self.target.class_name is not None and (
            det.class_name != self.target.class_name
        ):
            return False

        # Filter on minimum score if provided
        if self.target.score is not None and (  # noqa: SIM103
            det.score is None or det.score < self.target.score
        ):
            return False

        # If we got here, all provided constraints passed
        return True

@register_event
class AltitudeReached(Event):
    """
    True if telemetry reports being within tolerance of altitude.
    """

    altitude: float = Field(description="Target altitude.")
    tol: float = Field(0.5, ge=0, description="Error tolerance around target altitude.")
    use_absolute: bool = Field(False, description="Whether to use absolute altitude (MSL) instead of AGL altitude.")

    async def check(self) -> bool:
        while True:
            tel: DriverTelemetry | None = await fetch_telemetry()
            if not tel or not tel.position_info:
                continue
            if self.use_absolute:
                cur = tel.position_info.global_position
                if not cur:
                    continue
                if abs(cur.altitude - self.altitude) <= self.tol:
                    return True
            else:
                cur = tel.position_info.relative_position
                if not cur:
                    continue
                if abs(cur.z - self.altitude) <= self.tol:
                    return True

@register_event
class BoundingBoxCentered(Event):
    """
    True if the bounding box of the given class is centered in frame.
    """

    target: Detection = Field(description="Detection to check if centered")
    compute_stream: str = Field("aruco_detector_engine", description="Name of compute stream to get results from")
    v_tol: float = Field(1.0, ge=0.0, description="Vertical tolerance")
    h_tol: float = Field(1.0, ge=0.0, description="Horizontal tolerance")

    # --- Camera / image geometry ---
    image_width: int = Field(1280, gt=0, description="Camera image width in pixels")
    image_height: int = Field(720, gt=0, description="Camera image height in pixels")
    hfov_deg: float = Field(69.0, gt=0, description="Horizontal FOV in degrees")
    vfov_deg: float = Field(43.0, gt=0, description="Vertical FOV in degrees")

    @property
    def _pixel_center(self) -> tuple[float, float]:
        logger.debug("pixel center: w=%d, h=%d", self.image_width, self.image_height)
        return (self.image_width / 2.0, self.image_height / 2.0)

    async def _compute_error(self, box: BoundingBox) -> tuple[float, float]:
        img_w, img_h = self.image_width, self.image_height
        cx, cy = self._pixel_center
        y_min_pix = box.y_min * img_h
        x_min_pix = box.x_min * img_w
        y_max_pix = box.y_max * img_h
        x_max_pix = box.x_max * img_w

        target_x_pix = x_min_pix + (x_max_pix - x_min_pix) / 2.0
        target_y_pix = y_min_pix + (y_max_pix - y_min_pix) / 2.0

        h_err = ((target_x_pix - cx) / cx) * (self.hfov_deg / 2.0)
        v_err = -1 * ((target_y_pix - cy) / cy) * (self.vfov_deg / 2.0)
        return v_err, h_err

    async def check(self) -> bool:
        while True:
            res: FrameResult = await fetch_results('object-engine')
            box: BoundingBox | None = None
            if not res or not res.result:
                logger.info(f'{res=}')
                continue
            logger.info(res.result)
            for compute in res.result:
                det_result = compute.detection_result
                if not det_result or not det_result.detections:
                    continue
                for det in det_result.detections:
                    if det is None:
                        continue
                    if self.target.class_name is not None and (det.class_name == self.target.class_name):
                        box = det.bbox
                        break

            if box is not None:
                v_err, h_err = await self._compute_error(box)
                if math.isclose(v_err, 0.0, abs_tol=self.v_tol) and math.isclose(h_err, 0.0, abs_tol=self.h_tol):
                    return True

@register_event
class HSVReached(Event):
    """
    True if any result reports HSV close to target, or 'hsv_pass': true.
    Looks only in ComputeResult.generic_result (JSON).
    """

    target: HSV = Field(description="Target HSV color values (h: 0-179, s: 0-255, v: 0-255). Only provided components are checked.")
    tol: int = Field(15, ge=0, description="Allowed absolute error per HSV component.")

    async def check(self) -> bool:
        # Continuously read FrameResult messages and inspect generic_result JSON.
        while True:
            res: FrameResult = await fetch_results("object-engine")

            if not res or not res.result:
                continue

            for compute in res.result:
                if not compute.generic_result:
                    continue

                try:
                    payload = json.loads(compute.generic_result)
                except Exception:
                    # Ignore malformed JSON
                    continue

                # Shortcut: explicit pass flag
                if payload.get("hsv_pass") is True:
                    return True

                # Try to read HSV values from JSON; adjust to whatever structure you use
                h = payload.get("h")
                s = payload.get("s")
                v = payload.get("v")

                if self._matches_hsv(h, s, v):
                    return True

    def _matches_hsv(
        self,
        h: int | None,
        s: int | None,
        v: int | None,
    ) -> bool:
        def close(a: int | None, b: int | None) -> bool:
            if a is None or b is None:
                return False
            return abs(a - b) <= self.tol

        tgt = self.target
        checked_any = False

        if tgt.h is not None:
            checked_any = True
            if not close(h, tgt.h):
                return False

        if tgt.s is not None:
            checked_any = True
            if not close(s, tgt.s):
                return False

        if tgt.v is not None:
            checked_any = True
            if not close(v, tgt.v):
                return False

        # If no components were specified on target, don't treat it as a match
        return checked_any
