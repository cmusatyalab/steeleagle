from typing import AsyncIterator, List, Optional
import grpc
from .mission_store import MissionStore
from ..protocol.services.control_service_pb2_grpc import ControlStub
from ..protocol.services import control_service_pb2 as control_proto
from .datatypes.vehicle import (HeadingMode, AltitudeMode, ReferenceFrame, PoseMode, ImagingSensorConfiguration)
from .datatypes.common import Velocity, Location, Position, Response, Pose
from .datatypes.duration import Duration
from .utils import run_unary, run_streaming
from google.protobuf.json_format import ParseDict

import logging
logger = logging.getLogger(__name__)

class Vehicle:
    def __init__(self, channel: grpc.aio.Channel, mission_store: MissionStore):
        self.mission_store = mission_store
        self.control = ControlStub(channel)

    async def get_telemetry(self):
        source = "telemetry"
        return await self.mission_store.get_latest(source)

    async def connect(self) -> Response:
        req = control_proto.ConnectRequest()
        return await run_unary(self.control.Connect, req)

    async def disconnect(self) -> Response:
        req = control_proto.DisconnectRequest()
        return await run_unary(self.control.Disconnect, req)

    async def arm(self) -> Response:
        req = control_proto.ArmRequest()
        return await run_unary(self.control.Arm, req)

    async def disarm(self) -> Response:
        req = control_proto.DisarmRequest()
        return await run_unary(self.control.Disarm, req)

    async def joystick(self, velocity: Velocity, duration: Duration) -> AsyncIterator[Response]:
        req = control_proto.JoystickRequest()
        ParseDict(velocity.model_dump(), req.velocity)
        ParseDict(duration.model_dump(), req.duration)
        return await run_unary(self.control.Joystick, req)

    async def take_off(self, take_off_altitude: float) -> AsyncIterator[Response]:
        req = control_proto.TakeOffRequest()
        req.take_off_altitude = float(take_off_altitude)
        async for msg in run_streaming(self.control.TakeOff, req):
            yield msg

    async def land(self) -> AsyncIterator[Response]:
        req = control_proto.LandRequest()
        async for msg in run_streaming(self.control.Land, req):
            yield msg

    async def hold(self) -> AsyncIterator[Response]:
        req = control_proto.HoldRequest()
        async for msg in run_streaming(self.control.Hold, req):
            yield msg

    async def kill(self) -> AsyncIterator[Response]:
        req = control_proto.KillRequest()
        async for msg in run_streaming(self.control.Kill, req):
            yield msg

    async def set_home(self, location: Location) -> AsyncIterator[Response]:
        req = control_proto.SetHomeRequest()
        ParseDict(location.model_dump(), req.location)
        return await run_unary(self.control.SetHome, req)

    async def return_to_home(self) -> AsyncIterator[Response]:
        req = control_proto.ReturnToHomeRequest()
        async for msg in run_streaming(self.control.ReturnToHome, req):
            yield msg

    async def set_global_position(
        self,
        location: Location,
        heading_mode: Optional[HeadingMode] = None,
        altitude_mode: Optional[AltitudeMode] = None,
        max_velocity: Optional[Velocity] = None,
    ) -> AsyncIterator[Response]:
        req = control_proto.SetGlobalPositionRequest()
        ParseDict(location.model_dump(), req.location)
        if heading_mode is not None:
            req.heading_mode = heading_mode
        if altitude_mode is not None:
            req.altitude_mode = altitude_mode
        if max_velocity is not None:
            ParseDict(max_velocity.model_dump(), req.max_velocity)
        async for msg in run_streaming(self.control.SetGlobalPosition, req):
            yield msg

    async def set_relative_position(
        self,
        position: Position,
        max_velocity: Optional[Velocity] = None,
        frame: Optional[ReferenceFrame] = None,
    ) -> AsyncIterator[Response]:
        req = control_proto.SetRelativePositionRequest()
        ParseDict(position.model_dump(), req.position)
        if max_velocity is not None:
            ParseDict(max_velocity.model_dump(), req.max_velocity)
        if frame is not None:
            req.frame = frame
        async for msg in run_streaming(self.control.SetRelativePosition, req):
            yield msg

    async def set_velocity(
        self,
        velocity: Velocity,
        frame: Optional[ReferenceFrame] = None,
    ) -> AsyncIterator[Response]:
        req = control_proto.SetVelocityRequest()
        ParseDict(velocity.model_dump(), req.velocity)
        if frame is not None:
            req.frame = frame
        async for msg in run_streaming(self.control.SetVelocity, req):
            yield msg

    async def set_heading(
        self,
        location: Location,
        heading_mode: Optional[HeadingMode] = None,
    ) -> AsyncIterator[Response]:
        req = control_proto.SetHeadingRequest()
        ParseDict(location.model_dump(), req.location)
        if heading_mode is not None:
            req.heading_mode = heading_mode
        async for msg in run_streaming(self.control.SetHeading, req):
            yield msg

    async def set_gimbal_pose(
        self,
        gimbal_id: int,
        pose: Pose,
        pose_mode: Optional[PoseMode] = None,
        frame: Optional[ReferenceFrame] = None,
    ) -> AsyncIterator[Response]:
        req = control_proto.SetGimbalPoseRequest()
        req.gimbal_id = int(gimbal_id)
        ParseDict(pose.model_dump(), req.pose)
        if pose_mode is not None:
            req.pose_mode = pose_mode
        if frame is not None:
            req.frame = frame
        async for msg in run_streaming(self.control.SetGimbalPose, req):
            yield msg

    async def configure_imaging_sensor_stream(
        self,
        configurations: List[ImagingSensorConfiguration],
    ) -> Response:
        req = control_proto.ConfigureImagingSensorStreamRequest()
        for c in configurations:
            ParseDict(c.model_dump()(exclude_none=True), req.configurations.add())
        return await run_unary(self.control.ConfigureImagingSensorStream, req)

    async def configure_telemetry_stream(self, frequency: int) -> Response:
        req = control_proto.ConfigureTelemetryStreamRequest()
        req.frequency = int(frequency)
        return await run_unary(self.control.ConfigureTelemetryStream, req)