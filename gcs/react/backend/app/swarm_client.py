from collections.abc import AsyncIterator

from google.protobuf.message import Message
from pydantic import BaseModel
from steeleagle_protocol.v1 import common_pb2
from steeleagle_protocol.v1.services.driver import control_pb2
from steeleagle_protocol.v1.services.mission import mission_pb2
from steeleagle_protocol.v1.services.swarm import swarm_pb2, swarm_pb2_grpc


class VehicleResult(BaseModel):
    vehicle: str
    success: bool
    details: str = ""


async def _collect_stream(stream: AsyncIterator[Message]) -> list[VehicleResult]:
    results: list[VehicleResult] = []
    async for response in stream:
        results.append(
            VehicleResult(
                vehicle=response.vehicle,
                success=(response.code == 0),
                details=response.details,
            )
        )
    return results


class SwarmClient:
    """Thin wrapper over SwarmServiceStub: one typed method per swarm action,
    each returning the per-vehicle outcomes of a single fan-out call."""

    def __init__(self, stub: swarm_pb2_grpc.SwarmServiceStub) -> None:
        self._stub = stub

    async def start_mission(self, vehicles: list[str]) -> list[VehicleResult]:
        request = swarm_pb2.SwarmStartMissionRequest(
            vehicles=vehicles, request=mission_pb2.StartMissionRequest()
        )
        return await _collect_stream(self._stub.SwarmStartMission(request))

    async def take_off(
        self, vehicles: list[str], altitude: float
    ) -> list[VehicleResult]:
        request = swarm_pb2.SwarmTakeOffRequest(
            vehicles=vehicles,
            request=control_pb2.TakeOffRequest(take_off_altitude=altitude),
        )
        return await _collect_stream(self._stub.SwarmTakeOff(request))

    async def land(self, vehicles: list[str]) -> list[VehicleResult]:
        request = swarm_pb2.SwarmLandRequest(
            vehicles=vehicles, request=control_pb2.LandRequest()
        )
        return await _collect_stream(self._stub.SwarmLand(request))

    async def hold(self, vehicles: list[str]) -> list[VehicleResult]:
        request = swarm_pb2.SwarmHoldRequest(
            vehicles=vehicles, request=control_pb2.HoldRequest()
        )
        return await _collect_stream(self._stub.SwarmHold(request))

    async def return_to_home(self, vehicles: list[str]) -> list[VehicleResult]:
        request = swarm_pb2.SwarmReturnToHomeRequest(
            vehicles=vehicles, request=control_pb2.ReturnToHomeRequest()
        )
        return await _collect_stream(self._stub.SwarmReturnToHome(request))

    async def stop_mission(self, vehicles: list[str]) -> list[VehicleResult]:
        request = swarm_pb2.SwarmStopMissionRequest(
            vehicles=vehicles, request=mission_pb2.StopMissionResponse()
        )
        return await _collect_stream(self._stub.SwarmStopMission(request))

    async def set_velocity(
        self,
        vehicles: list[str],
        x_vel: float,
        y_vel: float,
        z_vel: float,
        angular_vel: float,
    ) -> list[VehicleResult]:
        request = swarm_pb2.SwarmSetVelocityRequest(
            vehicles=vehicles,
            request=control_pb2.SetVelocityRequest(
                velocity=common_pb2.Velocity(
                    x_vel=x_vel, y_vel=y_vel, z_vel=z_vel, angular_vel=angular_vel
                )
            ),
        )
        return await _collect_stream(self._stub.SwarmSetVelocity(request))

    async def set_gimbal_pose(
        self, vehicles: list[str], pitch: float, yaw: float, roll: float
    ) -> list[VehicleResult]:
        request = swarm_pb2.SwarmSetGimbalPoseRequest(
            vehicles=vehicles,
            request=control_pb2.SetGimbalPoseRequest(
                gimbal_id=0,
                pose=common_pb2.Pose(pitch=pitch, yaw=yaw, roll=roll),
                pose_mode=control_pb2.POSE_MODE_OFFSET,
            ),
        )
        return await _collect_stream(self._stub.SwarmSetGimbalPose(request))

    async def upload_mission(
        self, vehicles: list[str], mission_json: str, kml_map: bytes
    ) -> list[VehicleResult]:
        request = swarm_pb2.SwarmUploadMissionRequest(
            vehicles=vehicles,
            request=mission_pb2.UploadMissionRequest(
                mission=mission_pb2.MissionData(json=mission_json, map=kml_map)
            ),
        )
        return await _collect_stream(self._stub.SwarmUploadMission(request))
