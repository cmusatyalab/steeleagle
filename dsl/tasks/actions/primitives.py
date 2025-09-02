
from tasks.base import ExecutableAction
from typing import Optional
from compiler.registry import register_action

# ===== Low-Level Actions =====
@register_action
class TakeOff(ExecutableAction):
    async def execute(self, context):
        return await context['ctrl'].take_off()

@register_action
class Land(ExecutableAction):
    async def execute(self, context):
        return await context['ctrl'].land()

@register_action
class ReturnToHome(ExecutableAction):
    async def execute(self, context):
        return await context['ctrl'].rth()

@register_action
class Hover(ExecutableAction):
    async def execute(self, context):
        return await context['ctrl'].hover()

@register_action
class SetGPSLocation(ExecutableAction):
    lat: float
    lng: float
    alt: float
    bearing: Optional[float] = 0.0

    async def execute(self, context):
        return await context['ctrl'].set_gps_location(self.lat, self.lng, self.alt, self.bearing)

@register_action
class SetRelativePositionENU(ExecutableAction):
    north: float
    east: float
    up: float
    angle: float

    async def execute(self, context):
        return await context['ctrl'].set_relative_position_enu(self.north, self.east, self.up, self.angle)

@register_action
class SetRelativePositionBody(ExecutableAction):
    forward: float
    right: float
    up: float
    angle: float

    async def execute(self, context):
        return await context['ctrl'].set_relative_position_body(self.forward, self.right, self.up, self.angle)

@register_action
class SetVelocityENU(ExecutableAction):
    north_vel: float
    east_vel: float
    up_vel: float
    angle_vel: float

    async def execute(self, context):
        return await context['ctrl'].set_velocity_enu(self.north_vel, self.east_vel, self.up_vel, self.angle_vel)

@register_action
class SetVelocityBody(ExecutableAction):
    forward_vel: float
    right_vel: float
    up_vel: float
    angle_vel: float

    async def execute(self, context):
        return await context['ctrl'].set_velocity_body(self.forward_vel, self.right_vel, self.up_vel, self.angle_vel)

@register_action
class SetGimbalPose(ExecutableAction):
    pitch: float = 0.0
    roll: float = 0.0
    yaw: float = 0.0

    async def execute(self, context):
        return await context['ctrl'].set_gimbal_pose(self.pitch, self.roll, self.yaw)

@register_action
class ClearComputeResult(ExecutableAction):
    compute_type: str

    async def execute(self, context):
        return await context['ctrl'].clear_compute_result(self.compute_type)

@register_action
class ConfigureCompute(ExecutableAction):
    model: str
    hsv_lower: tuple[int, int, int]
    hsv_upper: tuple[int, int, int]

    async def execute(self, context):
        return await context['ctrl'].configure_compute(self.model, self.hsv_lower, self.hsv_upper)
