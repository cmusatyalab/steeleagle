# tasks/actions/procedures.py
import asyncio
from typing import Optional
from pydantic import Field
from compiler.registry import register_action
from tasks.base import ExecutableAction  # your BaseModel+async base
from tasks.actions.primitives import SetGimbalPose, SetGPSLocation, SetVelocityBody


@register_action
class ElevateToAltitude(ExecutableAction):
    target_altitude: float = Field(..., description="meters AGL/relative")
    tolerance: float = Field(0.2, ge=0.0, description="stop when within this of target")
    poll_period: float = Field(0.5, gt=0.0, description="seconds between telemetry polls")
    climb_speed: float = Field(1.0, description="m/s (adjust sign for your FCU if needed)")
    max_duration: Optional[float] = Field(60.0, gt=0.0, description="seconds; None = no limit")

    async def execute(self, context):
        start = asyncio.get_event_loop().time()
        while True:
            tel = await context['data'].get_telemetry()
            rel_alt = tel['global_position']['relative_altitude']

            if rel_alt + self.tolerance >= self.target_altitude:
                break
            
            set_vel = SetVelocityBody(0.0, 0.0, self.climb_speed, 0.0)
            await set_vel.execute(context)

            if self.max_duration is not None:
                if asyncio.get_event_loop().time() - start > self.max_duration:
                    raise TimeoutError(
                        f"ElevateToAltitude timed out after {self.max_duration}s "
                        f"(current={rel_alt}, target={self.target_altitude})"
                    )
            await asyncio.sleep(self.poll_period)


@register_action
class PrePatrolSequence(ExecutableAction):
    altitude: float = Field(15.0, gt=0.0, description="meters AGL/relative")
    gimbal_pitch: float = Field(0.0, description="degrees; 0=forward, positive=down")
    async def execute(self, context):
        await ElevateToAltitude(target_altitude=15.0).execute(context)
        await SetGimbalPose(pitch=0.0, yaw=0.0, roll=0.0).execute(context)


@register_action
class Patrol(ExecutableAction):
    area: str = Field(..., min_length=1, description="dot-path into waypoint map")
    hover_time: float = Field(1.0, ge=0.0, description="seconds to hover after each move")
    alt: Optional[float] = Field(default=None, description="altitude to use for each waypoint")

    async def execute(self, context):
        points = await context['data'].get_waypoints(self.area_path)
        if not points:
            raise RuntimeError(f"No waypoints found for '{self.area_path}'")

        for p in points:
            goto = SetGPSLocation(
                lat=float(p['lat']),
                lng=float(p['lng']),
                alt=self.alt if self.alt is not None else p.get('alt', 10.0),
                bearing=p.get('bearing', 0.0)
            )
            await goto.execute(context)

            if self.hover_time > 0:
                await asyncio.sleep(self.hover_time)



@register_action
class Track(ExecutableAction):
    target: str = Field(..., min_length=1, description="e.g., 'person' or 'car'")
    hover_altitude: Optional[float] = Field(10.0, gt=0.0, description="meters AGL/relative")
    gimbal_pitch: Optional[float] = Field(0.0, description="degrees; 0=forward, positive=down")
    lost_timeout: Optional[float] = Field(5.0, gt=0.0, description="seconds to wait before giving up")

    async def execute(self, context):
        pass