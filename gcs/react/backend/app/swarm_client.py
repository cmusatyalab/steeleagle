from collections.abc import AsyncIterator

from google.protobuf.message import Message
from pydantic import BaseModel
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
