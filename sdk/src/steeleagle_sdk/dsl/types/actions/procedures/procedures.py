# tasks/actions/procedures.py
import asyncio
import logging

from pydantic import Field

from ....compiler.registry import register_action
from ...base import Action
from ...datatypes import common as common
from ...datatypes.control import AltitudeMode, HeadingMode, ReferenceFrame
from ...datatypes.result import BoundingBox, Detection, FrameResult
from ...datatypes.waypoint import Waypoints
from ..primitives.vehicle import Joystick, SetGimbalPose, SetGlobalPosition, SetVelocity, SetGimbalPoseTarget

logger = logging.getLogger(__name__)
import numpy as np
from scipy.spatial.transform import Rotation as R

from ...utils import fetch_results, fetch_telemetry


@register_action
class ElevateToAltitude(Action):
    target_altitude: float = Field(..., description="meters AGL/relative")
    tolerance: float = Field(0.2, ge=0.0, description="stop when within this of target")
    poll_period: float = Field(
        0.5, gt=0.0, description="seconds between telemetry polls"
    )
    climb_speed: float = Field(
        1.0, description="m/s (adjust sign for your FCU if needed)"
    )
    max_duration: float | None = Field(
        None, gt=0.0, description="seconds; None = no limit"
    )

    async def execute(self):
        start = asyncio.get_event_loop().time()
        while True:
            tel = await fetch_telemetry()
            rel_alt = tel.position_info.relative_position.z

            if rel_alt + self.tolerance >= self.target_altitude:
                break

            set_vel = SetVelocity(
                velocity=common.Velocity(
                    x_vel=0.0,
                    y_vel=0.0,
                    z_vel=self.climb_speed,
                    angular_vel=0.0,
                ),
                frame=ReferenceFrame.ENU,  # or BODY
            )
            await set_vel.execute()

            if self.max_duration is not None and (
                asyncio.get_event_loop().time() - start > self.max_duration
            ):
                raise TimeoutError(
                    f"ElevateToAltitude timed out after {self.max_duration}s "
                    f"(current={rel_alt}, target={self.target_altitude})"
                )
            await asyncio.sleep(self.poll_period)


@register_action
class PrePatrolSequence(Action):
    altitude: float = Field(15.0, gt=0.0, description="meters AGL/relative")
    gimbal_pitch: float = Field(0.0, description="degrees; 0=forward, positive=down")

    async def execute(self):
        await ElevateToAltitude(target_altitude=15.0).execute()
        await SetGimbalPose(pitch=self.gimbal_pitch, yaw=0.0, roll=0.0).execute()


@register_action
class Patrol(Action):
    hover_time: float = Field(
        1.0, ge=0.0, description="seconds to hover after each move"
    )
    waypoints: Waypoints

    async def execute(self):
        map = self.waypoints.calculate()
        for area_name, points in map.items():
            logger.info("Patrol: area=%s, waypoints_num=%d", area_name, len(points))
            for p in points:
                logger.info(f"Patrol: goto {p}")
                goto = SetGlobalPosition(
                    location=common.Location(
                        latitude=float(p["lat"]),
                        longitude=float(p["lon"]),
                        altitude=float(p["alt"]),
                        heading=None,
                    ),
                    altitude_mode=AltitudeMode.RELATIVE,
                    heading_mode=HeadingMode.TO_TARGET,
                    max_velocity=common.Velocity(
                        x_vel=5.0, y_vel=5.0, z_vel=5.0, angular_vel=120.0
                    ),
                )
                await goto.execute()

                if self.hover_time > 0:
                    await asyncio.sleep(self.hover_time)


@register_action
class Track(Action):
    # --- Camera / image geometry ---
    image_width: int = Field(1280, gt=0, description="Camera image width in pixels")
    image_height: int = Field(720, gt=0, description="Camera image height in pixels")
    hfov_deg: float = Field(69.0, gt=0, description="Horizontal FOV in degrees")
    vfov_deg: float = Field(43.0, gt=0, description="Vertical FOV in degrees")
    compute_stream: str = Field(
        "openscout-object",
        description="Name of compute stream to pull detections from",
    )

    # --- Compute / detection configuration ---
    target: Detection
    leash_distance: float = Field(
        10, gt=0.0, description="leashing distance towards the tracked target"
    )
    target_lost_duration: float = Field(
        10.0, gt=0.0, description="Seconds without detection before exiting"
    )

    # --- actuation ---
    follow_speed: float = Field(1.0, ge=0.0, description="Max forward speed (m/s)")
    yaw_speed: float = Field(10.0, ge=0.0, description="Max yaw rate (deg/s)")
    orbit_speed: float = Field(0.0, ge=0.0, description="Lateral (orbit) speed (m/s)")
    yaw_gain: float = Field(
        2.0, ge=0.0, description="Gain applied to yaw error before sending to FCU"
    )

    # --- private ---
    _poll_period: float = 0.05

    @property
    def _pixel_center(self) -> tuple[float, float]:
        return (self.image_width / 2.0, self.image_height / 2.0)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return float(np.clip(value, minimum, maximum))

    def _find_intersection(
        self, target_dir: np.ndarray, target_insct: np.ndarray
    ) -> np.ndarray | None:
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        denom = plane_norm.dot(target_dir)
        if abs(denom) < 1e-6:
            return None

        t = (plane_norm.dot(plane_pt) - plane_norm.dot(target_insct)) / plane_norm.dot(
            target_dir
        )
        return target_insct + (t * target_dir)

    async def _estimate_distance(
        self, yaw_deg: float, pitch_deg: float, telemetry
    ) -> np.ndarray:
        alt = telemetry.position_info.relative_position.z
        gimbal_pitch_deg = telemetry.gimbal_info.gimbals[0].pose_body.pitch

        vf = np.array([0.0, 1.0, 0.0])
        r = R.from_euler(
            "ZYX", [yaw_deg, 0, pitch_deg + gimbal_pitch_deg], degrees=True
        )
        target_dir = r.as_matrix().dot(vf)
        target_vec = self._find_intersection(target_dir, np.array([0, 0, alt]))

        if target_vec is None:
            return np.zeros(3, dtype=float)
        target_norm = np.linalg.norm(target_vec)
        leash_vec = self.leash_distance * (target_vec / target_norm)

        return leash_vec - target_vec

    async def _compute_error(
        self, box: BoundingBox, telemetry
    ) -> tuple[float, float, float]:
        img_w, img_h = self.image_width, self.image_height
        cx, cy = self._pixel_center
        y_min_pix = box.y_min * img_h
        x_min_pix = box.x_min * img_w
        y_max_pix = box.y_max * img_h
        x_max_pix = box.x_max * img_w

        target_x_pix = x_min_pix + (x_max_pix - x_min_pix) / 2.0
        target_y_pix = y_min_pix + (y_max_pix - y_min_pix) / 2.0

        target_yaw_angle = ((target_x_pix - cx) / cx) * (self.hfov_deg / 2.0)
        target_pitch_angle = ((target_y_pix - cy) / cy) * (self.vfov_deg / 2.0)
        target_bottom_pitch = ((img_h - y_max_pix) - cy) / cy * (self.vfov_deg / 2.0)

        yaw_error = -1.0 * target_yaw_angle
        gimbal_error = target_pitch_angle

        follow_vec = await self._estimate_distance(
            target_yaw_angle, target_bottom_pitch, telemetry
        )
        follow_error = float(follow_vec[1] * -1.0)

        return (follow_error, yaw_error, gimbal_error)

    async def _actuate(
        self,
        follow_vel: float,
        yaw_vel_deg: float,
        gimbal_error_deg: float,
        orbit_speed: float,
        telemetry,
    ) -> None:
        prev_gimbal_pitch = telemetry.gimbal_info.gimbals[0].pose_body.pitch

        # Body-frame velocities: forward (x), lateral (y), vertical (z), yaw rate
        set_joystick = Joystick(
            velocity=common.Velocity(
                x_vel=follow_vel,
                y_vel=orbit_speed,
                angular_vel=yaw_vel_deg * self.yaw_gain,
            )
        )
        await set_joystick.execute()

        # Gimbal pitch command
        desired_pitch = (gimbal_error_deg * 0.5) + prev_gimbal_pitch
        set_gimbal = SetGimbalPoseTarget(pitch=desired_pitch, yaw=0.0, roll=0.0)
        await set_gimbal.execute()

    async def execute(self):
        last_seen: float | None = None
        while True:
            # --- Target lost check ---
            now = asyncio.get_event_loop().time()
            if last_seen is not None and (now - last_seen) > self.target_lost_duration:
                # Stop motion and exit
                telemetry = await fetch_telemetry()
                await self._actuate(0.0, 0.0, 0.0, 0.0, 0.0, telemetry)
                logger.info(
                    "Track: target lost for %.1fs, exiting",
                    now - last_seen,
                )
                break

            # --- Telemetry ---
            telemetry = await fetch_telemetry()

            # --- Detections ---
            res: FrameResult = await fetch_results(self.compute_stream)
            box: BoundingBox | None = None
            if not res or not res.result:
                continue  # no ComputeResult entries
            for compute in res.result:
                det_result = compute.detection_result
                if not det_result or not det_result.detections:
                    continue
                for det in det_result.detections:
                    if det is None:
                        continue
                    if self.target.class_name is not None and (
                        det.class_name == self.target.class_name
                    ):
                        box = det.bbox
                        last_seen = now
                        break

            # --- Track ---
            if box is not None:
                try:
                    follow_err, yaw_err, gimbal_err = await self._compute_error(
                        box, telemetry
                    )
                except Exception as e:
                    logger.error("Track: error computing tracking error: %s", e)
                    await asyncio.sleep(self._poll_period)
                    continue

                try:
                    follow_vel = self._clamp(
                        follow_err, -self.follow_speed, self.follow_speed
                    )
                    yaw_vel = self._clamp(yaw_err, -self.yaw_speed, self.yaw_speed)
                except Exception as e:
                    logger.error("Track: error clamping velocities: %s", e)
                    await asyncio.sleep(self._poll_period)
                    continue

                logger.info(
                    "Track: forward=%.3f, yaw=%.3f, gimbal=%.3f, orbit=%.3f",
                    follow_vel,
                    yaw_vel,
                    gimbal_err,
                    self.orbit_speed,
                )

                try:
                    # At/above desired altitude: follow + orbit
                    await self._actuate(
                        follow_vel=follow_vel,
                        yaw_vel_deg=yaw_vel,
                        gimbal_error_deg=gimbal_err,
                        orbit_speed=self.orbit_speed,
                        telemetry=telemetry,
                    )
                except Exception as e:
                    logger.error("Track: actuation failed: %s", e)

            await asyncio.sleep(self._poll_period)
