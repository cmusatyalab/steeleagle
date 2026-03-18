# tasks/actions/procedures.py
import asyncio
import logging
import math

from pydantic import Field

from ....compiler.registry import register_action
from ...base import Action
from ...datatypes import common as common
from ...datatypes.control import AltitudeMode, HeadingMode, ReferenceFrame, PoseMode
from ...datatypes.result import BoundingBox, Detection, FrameResult
from ...datatypes.waypoint import Waypoints
from ..primitives.vehicle import Joystick, SetGimbalPose, SetGlobalPosition, SetVelocity, SetGimbalPoseTarget, Hold, Land

logger = logging.getLogger(__name__)
import numpy as np
from scipy.spatial.transform import Rotation as R

from ...utils import fetch_results, fetch_telemetry


@register_action
class ElevateToAltitude(Action):
    """Climb to a target altitude by setting vertical velocity until reached."""

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
                frame=ReferenceFrame.NEU,  # or BODY
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
    """Elevate to altitude and set gimbal pitch before starting a patrol."""

    altitude: float = Field(15.0, gt=0.0, description="meters AGL/relative")
    gimbal_pitch: float = Field(0.0, description="degrees; 0=forward, positive=down")

    async def execute(self):
        await ElevateToAltitude(target_altitude=self.altitude).execute()
        await SetGimbalPose(
            gimbal_id=0,
            pose=common.Pose(pitch=self.gimbal_pitch, roll=0.0, yaw=0.0)
        ).execute()


@register_action
class Patrol(Action):
    """Fly through a sequence of waypoints generated from an area and slicing algorithm."""

    hover_time: float = Field(
        1.0, ge=0.0, description="seconds to hover after each move"
    )
    waypoints: Waypoints = Field(description="Waypoints definition (area, alt, algo, spacing, angle_degrees, trigger_distance).")
    max_velocity: common.Velocity = Field(
            common.Velocity(x_vel=5.0, y_vel=5.0, z_vel=5.0, angular_vel=120.0),
            description="Maximum velocity to use while transiting between waypoints.",
    )

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
                    max_velocity=self.max_velocity,
                )
                await goto.execute()

                if self.hover_time > 0:
                    await asyncio.sleep(self.hover_time)

@register_action
class PrecisionLand(Action):
    """Land on an object using vision-based control."""

    # --- Camera / image geometry ---
    image_width: int = Field(1280, gt=0, description="Camera image width in pixels")
    image_height: int = Field(720, gt=0, description="Camera image height in pixels")
    hfov_deg: float = Field(69.0, gt=0, description="Horizontal FOV in degrees")
    vfov_deg: float = Field(43.0, gt=0, description="Vertical FOV in degrees")
    err_tol: float = Field(1.0, ge=0)
    compute_stream: str = Field(
        "object-engine",
        description="Name of compute stream to pull detections from",
    )

    # --- Compute / detection configuration ---
    target: Detection = Field(description="Detection to track (class_name to match, optional score threshold)")
    target_lost_duration: float = Field(1.0)

    # --- Movement speeds ---
    forward_speed: float = Field(1.0, gt=0)
    lateral_speed: float = Field(1.0, gt=0)
    descent_speed: float = Field(1.0, gt=0)
    altitude_ceil: float = Field(10.0, lt=20.0)
    target_altitude: float = Field(1.5, gt=1)

    @property
    def _pixel_center(self) -> tuple[float, float]:
        logger.debug("pixel center: w=%d, h=%d", self.image_width, self.image_height)
        return (self.image_width / 2.0, self.image_height / 2.0)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        logger.debug("clamping value=%f, min=%f, max=%f", value, minimum, maximum)
        return float(np.clip(value, minimum, maximum))

    async def _compute_error(
        self, box: BoundingBox, telemetry
    ) -> tuple[float, float, float]:
        logger.debug("computing error for box=%s", box)
        img_w, img_h = self.image_width, self.image_height
        cx, cy = self._pixel_center
        y_min_pix = box.y_min * img_h
        x_min_pix = box.x_min * img_w
        y_max_pix = box.y_max * img_h
        x_max_pix = box.x_max * img_w

        target_x_pix = x_min_pix + (x_max_pix - x_min_pix) / 2.0
        target_y_pix = y_min_pix + (y_max_pix - y_min_pix) / 2.0

        lateral_error = ((target_x_pix - cx) / cx) * (self.hfov_deg / 2.0)
        forward_error = -1 * ((target_y_pix - cy) / cy) * (self.vfov_deg / 2.0)

        return forward_error, lateral_error

    async def execute(self):
        logger.info('Started the task')
        last_seen: float | None = None
        mode: int = 0
        checked_count: int = 0
        # Pitch the gimbal
        await SetGimbalPose(
            gimbal_id=0,
            pose=common.Pose(pitch=-90.0, roll=0.0, yaw=0.0)
        ).execute()
        # Descent loop
        while True:
            # --- Telemetry ---
            telemetry = await fetch_telemetry()
            # logger.info("Track: telemetry fetched: %s", telemetry)

            #--- Target lost check ---
            now = asyncio.get_event_loop().time()
            if last_seen is not None and (now - last_seen) > self.target_lost_duration:
                if altitude >= self.altitude_ceil:
                    await Hold().execute()
                    logger.info(
                        "PrecisionLand: target lost for %.1fs, exiting",
                        now - last_seen,
                    )
                    break
                else:
                    await Joystick(velocity=Velocity(z_vel=-self.descent_speed)).execute()

            # --- Detections ---
            res: FrameResult = await fetch_results(self.compute_stream)
            # logger.info("Track: fetched results from stream=%s", res)

            box: BoundingBox | None = None
            if not res or not res.result:
                logger.info("PrecisionLand: no objects found")
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

            # --- Track procedure ---
            if box is not None:
                telemetry = await fetch_telemetry()
                altitude = telemetry.position_info.relative_position.z
                forward_err, lateral_err = await self._compute_error(box, telemetry)
                forward_off = math.tan(math.radians(forward_err)) * altitude
                lateral_off = math.tan(math.radians(lateral_err)) * altitude
                target = common.Velocity()
                if mode == 0: # forward
                    logger.info(f'forward step {forward_off}')
                    if math.isclose(forward_off, 0.0, abs_tol=self.err_tol * altitude):
                        logger.info(f'forward check {forward_off} {self.err_tol * altitude} {altitude}')
                        checked_count += 1
                        await Hold().execute()
                        if checked_count >= 5:
                            checked_count = 0
                            mode = 1
                            continue
                    else:
                        checked_count = 0
                        target.x_vel = self._clamp(forward_off, -self.forward_speed, self.forward_speed)
                elif mode == 1: # lateral
                    logger.info(f'lateral step {lateral_off}')
                    if math.isclose(lateral_off, 0.0, abs_tol=self.err_tol * altitude):
                        logger.info(f'lateral check {lateral_off} {self.err_tol * altitude} {altitude}')
                        checked_count += 1
                        await Hold().execute()
                        if checked_count >= 5 and math.isclose(forward_off, 0.0, abs_tol=self.err_tol * altitude):
                            checked_count = 0
                            mode = 2
                            continue
                        elif checked_count >= 5:
                            checked_count = 0
                            mode = 0
                            continue
                    else:
                        checked_count = 0
                        target.y_vel = self._clamp(lateral_off, -self.lateral_speed, self.lateral_speed)
                else: # descend
                    logger.info('descend step')
                    if altitude > self.target_altitude:
                        logger.info('set descend speed')
                        if math.isclose(forward_off, 0.0, abs_tol=self.err_tol * altitude) and math.isclose(lateral_off, 0.0, abs_tol=self.err_tol * altitude):
                            target.z_vel = -1 * self.descent_speed
                        else:
                            mode = 0
                            await Hold().execute()
                            continue
                logger.info('outer loop')
                if math.isclose(forward_off, 0.0, abs_tol=self.err_tol) and math.isclose(lateral_off, 0.0, abs_tol=self.err_tol) and altitude <= self.target_altitude:
                    logger.info('land check')
                    await Land().execute()
                    return
                else:
                    logger.info('joystick')
                    await Joystick(velocity=target).execute()


@register_action
class Track(Action):
    """Track a detected object using vision-based control, adjusting yaw and gimbal to follow the target."""

    # --- Camera / image geometry ---
    image_width: int = Field(1280, gt=0, description="Camera image width in pixels")
    image_height: int = Field(720, gt=0, description="Camera image height in pixels")
    hfov_deg: float = Field(69.0, gt=0, description="Horizontal FOV in degrees")
    vfov_deg: float = Field(43.0, gt=0, description="Vertical FOV in degrees")
    compute_stream: str = Field(
        "object-engine",
        description="Name of compute stream to pull detections from",
    )

    # --- Compute / detection configuration ---
    target: Detection = Field(description="Detection to track (class_name to match, optional score threshold)")
    leash_distance: float = Field(
        10, ge=0.0, description="leashing distance towards the tracked target"
    )
    target_lost_duration: float = Field(
        10.0, gt=0.0, description="Seconds without detection before exiting"
    )

    # --- actuation ---
    follow_speed: float = Field(1.0, ge=0.0, description="Max planar speed (m/s)")
    yaw_speed: float = Field(10.0, ge=0.0, description="Max yaw rate (deg/s)")
    descent_speed: float = Field(0.0, ge=0.0, description="Descent speed (m/s)")
    yaw_gain: float = Field(
        2.0, ge=0.0, description="Gain applied to yaw error before sending to FCU"
    )
    follow_gain: float = Field(
        1.0, ge=0.0, description="Gain applied to follow error before sending to FCU"
    )
    target_altitude: float = Field(
        0.0, ge=0.0, description="Target altitude to descend to while tracking"
    )
    altitude_tolerance: float = Field(
        0.0, ge=0.0, description="Tolerance at which altitude will be checked for descending"
    )
    strafe: bool = Field(False, description="Whether or not to move left/right when following")
    gimbal_lock: bool = Field(False, description="Whether or not to lock the gimbal in position")

    # --- private ---
    _poll_period: float = 0.05

    @property
    def _pixel_center(self) -> tuple[float, float]:
        logger.debug("pixel center: w=%d, h=%d", self.image_width, self.image_height)
        return (self.image_width / 2.0, self.image_height / 2.0)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        logger.debug("clamping value=%f, min=%f, max=%f", value, minimum, maximum)
        return float(np.clip(value, minimum, maximum))

    def _find_intersection(
        self, tracker_dir: np.ndarray, tracker_location: np.ndarray
    ) -> np.ndarray | None:
        logger.debug("finding intersection for dir=%s, insct=%s", tracker_dir, tracker_location)
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        denom = plane_norm.dot(tracker_dir)
        if abs(denom) < 1e-6:
            return None

        t = (plane_norm.dot(plane_pt) - plane_norm.dot(tracker_location)) / denom
        return tracker_location + (t * tracker_dir)

    async def _estimate_distance(
        self, yaw_deg: float, pitch_deg: float, telemetry
    ) -> np.ndarray:
        logger.debug("estimating distance for yaw=%.2f, pitch=%.2f", yaw_deg, pitch_deg)
        alt = telemetry.position_info.relative_position.z
        gimbal_pitch_deg = telemetry.gimbal_info.gimbals[0].pose_neu.pitch

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

        return target_vec - leash_vec

    async def _compute_error(
        self, box: BoundingBox, telemetry
    ) -> tuple[float, float, float]:
        logger.debug("computing error for box=%s", box)
        img_w, img_h = self.image_width, self.image_height
        cx, cy = self._pixel_center
        y_min_pix = box.y_min * img_h
        x_min_pix = box.x_min * img_w
        y_max_pix = box.y_max * img_h
        x_max_pix = box.x_max * img_w

        target_x_pix = x_min_pix + (x_max_pix - x_min_pix) / 2.0
        target_y_pix = y_min_pix + (y_max_pix - y_min_pix) / 2.0

        target_yaw_angle = ((target_x_pix - cx) / cx) * (self.hfov_deg / 2.0)
        target_pitch_angle = -1 * ((target_y_pix - cy) / cy) * (self.vfov_deg / 2.0)
        target_bottom_pitch = ((img_h - y_max_pix) - cy) / cy * (self.vfov_deg / 2.0)

        yaw_error = target_yaw_angle
        gimbal_error = target_pitch_angle

        if self.strafe:
            follow_vec = await self._estimate_distance(
                target_yaw_angle, target_pitch_angle, telemetry
            )
        else:
            follow_vec = await self._estimate_distance(
                target_yaw_angle, target_bottom_pitch, telemetry
            )

        return (follow_vec, yaw_error, gimbal_error)

    async def _actuate(
        self,
        forward_vel: float,
        right_vel: float,
        yaw_vel_deg: float,
        descent_speed: float,
        gimbal_error_deg: float,
        telemetry,
    ) -> None:
        logger.debug(
            "actuating: right_vel=%.3f, forward_vel=%.3f, yaw_vel=%.3f, descent_speed: %.3f, gimbal_error=%.3f",
            right_vel,
            forward_vel,
            yaw_vel_deg,
            descent_speed,
            gimbal_error_deg,
        )

        # Check to see if we need to descend any more
        rel_alt = telemetry.position_info.relative_position.z
        if rel_alt + self.altitude_tolerance <= self.target_altitude:
            descent_speed = 0.0

        # Body-frame velocities: forward (x), lateral (y), vertical (z), yaw rate
        if not self.strafe:
            velocity_target = common.Velocity(
                    x_vel=forward_vel * self.follow_gain,
                    y_vel=0.0,
                    z_vel=-1 * descent_speed,
                    angular_vel= yaw_vel_deg * self.yaw_gain,
            )
        else:
            velocity_target = common.Velocity(
                    x_vel=forward_vel * self.follow_gain,
                    y_vel=yaw_vel_deg * self.yaw_gain,
                    z_vel=-1 * descent_speed,
                    angular_vel=0.0,
            )
        logger.debug("Actuate: velocity target: %s", velocity_target)
        set_joystick = Joystick(
            velocity=velocity_target
        )
        await set_joystick.execute()

        # Gimbal pitch command
        if not self.gimbal_lock:
            desired_pitch = (gimbal_error_deg * 0.5)
            pose = common.Pose(
                pitch=desired_pitch,
                yaw=0.0,
                roll=0.0,
            )
            # gimbal_id = telemetry.gimbal_info.gimbals[0].gimbal_id
            set_gimbal = SetGimbalPoseTarget(gimbal_id = 0, pose = pose, pose_mode=PoseMode.OFFSET, frame=None)
            await set_gimbal.execute()

    async def execute(self):
        last_seen: float | None = None
        while True:
            #--- Target lost check ---
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
            # logger.info("Track: telemetry fetched: %s", telemetry)

            # --- Detections ---
            res: FrameResult = await fetch_results(self.compute_stream)
            # logger.info("Track: fetched results from stream=%s", res)

            box: BoundingBox | None = None
            if not res or not res.result:
                logger.info("Track: no objects found")
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
                    follow_vel = [0.0, 0.0]
                    follow_vel[0] = self._clamp(
                        follow_err[0], -self.follow_speed, self.follow_speed
                    )
                    follow_vel[1] = self._clamp(
                        follow_err[1], -self.follow_speed, self.follow_speed
                    )
                    yaw_vel = self._clamp(yaw_err, -self.yaw_speed, self.yaw_speed)
                    logger.debug(f"follow_vel {follow_err}")
                    logger.debug("yaw_speed=%s yaw_err=%.3f yaw_vel(after clamp)=%.3f", self.yaw_speed, yaw_err, yaw_vel)
                    logger.debug("follow_err_forward=%.3f, follow_err_right=%.3f", follow_vel[0], follow_vel[1])

                except Exception as e:
                    logger.error("Track: error clamping velocities: %s", e)
                    await asyncio.sleep(self._poll_period)
                    continue

                logger.debug(
                    "Track: right=%.3f, forward=%.3f, yaw=%.3f, descend=%.3f, gimbal=%.3f",
                    follow_vel[0],
                    follow_vel[1],
                    yaw_vel,
                    self.descent_speed,
                    gimbal_err,
                )

                try:
                    # At/above desired altitude: follow
                    await self._actuate(
                        forward_vel=follow_vel[1],
                        right_vel=follow_vel[0],
                        yaw_vel_deg=yaw_vel,
                        descent_speed=self.descent_speed,
                        gimbal_error_deg=gimbal_err,
                        telemetry=telemetry,
                    )
                except Exception as e:
                    logger.error("Track: actuation failed: %s", e)

            await asyncio.sleep(self._poll_period)
