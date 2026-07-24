import grpc
import pytest
from steeleagle_protocol.v1.services.swarm import swarm_pb2, swarm_pb2_grpc

from app.swarm_client import SwarmClient, VehicleResult


class FakeSwarmServicer(swarm_pb2_grpc.SwarmServiceServicer):
    """Fake SwarmService for tests.

    `script[rpc_name]` is either a list of (vehicle, code, details) tuples to
    stream back as responses, or an Exception instance whose message aborts
    the call with UNAVAILABLE. Every request received is recorded in
    `self.received[rpc_name]` so tests can assert on what was actually sent.
    """

    def __init__(self, script: dict):
        self._script = script
        self.received: dict[str, list] = {}

    async def _run(self, rpc_name, response_cls, request, context):
        self.received.setdefault(rpc_name, []).append(request)
        outcome = self._script[rpc_name]
        if isinstance(outcome, Exception):
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(outcome))
            return
        for vehicle, code, details in outcome:
            yield response_cls(vehicle=vehicle, code=code, details=details)

    async def SwarmStartMission(self, request, context):
        async for r in self._run(
            "SwarmStartMission", swarm_pb2.SwarmStartMissionResponse, request, context
        ):
            yield r


@pytest.fixture
async def swarm_client_factory():
    servers = []

    async def _make(script: dict) -> tuple[SwarmClient, FakeSwarmServicer]:
        servicer = FakeSwarmServicer(script)
        server = grpc.aio.server()
        swarm_pb2_grpc.add_SwarmServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        servers.append(server)
        channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
        client = SwarmClient(swarm_pb2_grpc.SwarmServiceStub(channel))
        return client, servicer

    yield _make

    for server in servers:
        await server.stop(None)


async def test_start_mission_all_succeed(swarm_client_factory):
    client, _ = await swarm_client_factory(
        {"SwarmStartMission": [("drone1", 0, ""), ("drone2", 0, "")]}
    )

    results = await client.start_mission(["drone1", "drone2"])

    assert results == [
        VehicleResult(vehicle="drone1", success=True, details=""),
        VehicleResult(vehicle="drone2", success=True, details=""),
    ]


async def test_start_mission_partial_failure(swarm_client_factory):
    client, _ = await swarm_client_factory(
        {"SwarmStartMission": [("drone1", 0, ""), ("drone2", 13, "internal error")]}
    )

    results = await client.start_mission(["drone1", "drone2"])

    assert results[0] == VehicleResult(vehicle="drone1", success=True, details="")
    assert results[1] == VehicleResult(
        vehicle="drone2", success=False, details="internal error"
    )


async def test_start_mission_channel_failure(swarm_client_factory):
    client, _ = await swarm_client_factory(
        {"SwarmStartMission": RuntimeError("swarm controller down")}
    )

    with pytest.raises(grpc.aio.AioRpcError):
        await client.start_mission(["drone1"])
