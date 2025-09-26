# tasks/actions/procedures.py
import asyncio
from typing import Optional
from pydantic import Field
from ....dsl.compiler.registry import register_action
from ...base import Action
from ..primitives.control import SetGimbalPose, SetGlobalPosition, SetVelocity
from ...datatypes import common as common
from ...datatypes.waypoint import Waypoints
import logging
logger = logging.getLogger(__name__)

@register_action
class ElevateToAltitude(Action):
    target_altitude: float = Field(..., description="meters AGL/relative")
    tolerance: float = Field(0.2, ge=0.0, description="stop when within this of target")
    poll_period: float = Field(0.5, gt=0.0, description="seconds between telemetry polls")
    climb_speed: float = Field(1.0, description="m/s (adjust sign for your FCU if needed)")
    max_duration: Optional[float] = Field(60.0, gt=0.0, description="seconds; None = no limit")

    async def execute(self):
        start = asyncio.get_event_loop().time()
        while True:
            tel = None # await context["data"].get_telemetry() # by telemetry handler
            rel_alt = tel['global_position']['relative_altitude']

            if rel_alt + self.tolerance >= self.target_altitude:
                break
            
            set_vel = SetVelocity(
                velocity=common.Velocity(
                    x_vel=0.0,
                    y_vel=0.0,
                    up_vel=self.climb_speed,
                    angular_vel=0.0,
                ),
                frame=SetVelocity.ReferenceFrame.ENU,  # or BODY
            )
            await set_vel.execute()

            if self.max_duration is not None:
                if asyncio.get_event_loop().time() - start > self.max_duration:
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
    hover_time: float = Field(1.0, ge=0.0, description="seconds to hover after each move")
    waypoints: Waypoints

    async def execute(self, context):
        map = self.waypoints.calculate()
        for area_name, points in map.items():
            logger.info("Patrol: area=%s, segments=%d", area_name, len(points))
            for p in points:
                goto = SetGlobalPosition(
                    location=common.Location(
                        latitude=float(p["lat"]),
                        longitude=float(p["lng"]),
                        altitude=float(p["alt"]),
                    ),
                    altitude_mode=SetGlobalPosition.AltitudeMode.RELATIVE,
                    heading_mode=SetGlobalPosition.HeadingMode.TO_TARGET,
                    max_velocity=common.Velocity(x_vel=0.0, y_vel=5.0, up_vel=0.0, angular_vel=0.0),
                )
                await goto.execute(context)

                if self.hover_time > 0:
                    await asyncio.sleep(self.hover_time)



@register_action
class Track(Action):
    target: str = Field(..., min_length=1, description="e.g., 'person' or 'car'")
    hover_altitude: Optional[float] = Field(10.0, gt=0.0, description="meters AGL/relative")
    gimbal_pitch: Optional[float] = Field(0.0, description="degrees; 0=forward, positive=down")
    lost_timeout: Optional[float] = Field(5.0, gt=0.0, description="seconds to wait before giving up")

    async def execute(self, context):
        pass
