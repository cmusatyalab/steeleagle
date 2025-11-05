from typing import AsyncIterator, List, Optional
import grpc
from google.protobuf.duration_pb2 import Duration
from .mission_store import MissionStore
from ..protocol.services.control_service_pb2_grpc import ControlStub
from ..protocol.services import control_service_pb2 as control_proto
from .datatypes.vehicle import (HeadingMode, AltitudeMode, ReferenceFrame, PoseMode, ImagingSensorConfiguration)
from .datatypes.common import Velocity, Location, Position, Response, Pose
from .utils import run_unary, run_streaming


class Vehicle:
    def __init__(self, mission_store: MissionStore, channel: str, vehicle_id: str):
        self.mission_store = mission_store
        stub_channel = grpc.aio.insecure_channel(channel)
        self.control = ControlStub(stub_channel)
        self.vehicle_id = vehicle_id

    async def get_telemetry(self):
        source = "telemetry"
        topic = self.vehicle_id
        return await self.mission_store.get_latest(source, topic)

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
        req.velocity.CopyFrom(velocity)
        req.duration.CopyFrom(duration)
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
        req.location.CopyFrom(location)
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
        req.location.CopyFrom(location)
        if heading_mode is not None:
            req.heading_mode = heading_mode
        if altitude_mode is not None:
            req.altitude_mode = altitude_mode
        if max_velocity is not None:
            req.max_velocity.CopyFrom(max_velocity)
        async for msg in run_streaming(self.control.SetGlobalPosition, req):
            yield msg

    async def set_relative_position(
        self,
        position: Position,
        max_velocity: Optional[Velocity] = None,
        frame: Optional[ReferenceFrame] = None,
    ) -> AsyncIterator[Response]:
        req = control_proto.SetRelativePositionRequest()
        req.position.CopyFrom(position)
        if max_velocity is not None:
            req.max_velocity.CopyFrom(max_velocity)
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
        req.velocity.CopyFrom(velocity)
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
        req.location.CopyFrom(location)
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
        req.pose.CopyFrom(pose)
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
        req.configurations.extend(configurations)
        return await run_unary(self.control.ConfigureImagingSensorStream, req)

    async def configure_telemetry_stream(self, frequency: int) -> Response:
        req = control_proto.ConfigureTelemetryStreamRequest()
        req.frequency = int(frequency)
        return await run_unary(self.control.ConfigureTelemetryStream, req)
