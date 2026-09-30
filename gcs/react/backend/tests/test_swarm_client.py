import hashlib

import grpc
import pytest
from steeleagle_protocol.v1.services.driver import control_pb2
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

    async def SwarmTakeOff(self, request, context):
        async for r in self._run(
            "SwarmTakeOff", swarm_pb2.SwarmTakeOffResponse, request, context
        ):
            yield r

    async def SwarmLand(self, request, context):
        async for r in self._run(
            "SwarmLand", swarm_pb2.SwarmLandResponse, request, context
        ):
            yield r

    async def SwarmHold(self, request, context):
        async for r in self._run(
            "SwarmHold", swarm_pb2.SwarmHoldResponse, request, context
        ):
            yield r

    async def SwarmReturnToHome(self, request, context):
        async for r in self._run(
            "SwarmReturnToHome", swarm_pb2.SwarmReturnToHomeResponse, request, context
        ):
            yield r

    async def SwarmStopMission(self, request, context):
        async for r in self._run(
            "SwarmStopMission", swarm_pb2.SwarmStopMissionResponse, request, context
        ):
            yield r

    async def SwarmSetVelocityTarget(self, request, context):
        async for r in self._run(
            "SwarmSetVelocityTarget",
            swarm_pb2.SwarmSetVelocityTargetResponse,
            request,
            context,
        ):
            yield r

    async def SwarmSetGimbalAngleTarget(self, request, context):
        async for r in self._run(
            "SwarmSetGimbalAngleTarget",
            swarm_pb2.SwarmSetGimbalAngleTargetResponse,
            request,
            context,
        ):
            yield r

    async def SwarmUploadMission(self, request_iterator, context):
        requests = [r async for r in request_iterator]
        self.received.setdefault("SwarmUploadMission", []).append(requests)
        outcome = self._script["SwarmUploadMission"]
        if isinstance(outcome, Exception):
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(outcome))
            return
        for item in outcome:
            if item[0] == "progress":
                _, vehicle, sent, total = item
                yield swarm_pb2.SwarmUploadMissionResponse(
                    vehicle=vehicle,
                    progress=swarm_pb2.UploadProgress(sent=sent, total=total),
                )
            else:
                vehicle, code, details = item
                yield swarm_pb2.SwarmUploadMissionResponse(
                    vehicle=vehicle, code=code, details=details
                )


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


async def test_take_off_sends_altitude(swarm_client_factory):
    client, servicer = await swarm_client_factory({"SwarmTakeOff": [("drone1", 0, "")]})

    await client.take_off(["drone1"], altitude=12.5)

    sent = servicer.received["SwarmTakeOff"][0]
    assert list(sent.vehicles) == ["drone1"]
    assert sent.request.altitude == pytest.approx(12.5)


async def test_land(swarm_client_factory):
    client, _ = await swarm_client_factory({"SwarmLand": [("drone1", 0, "")]})

    results = await client.land(["drone1"])

    assert results == [VehicleResult(vehicle="drone1", success=True, details="")]


async def test_hold(swarm_client_factory):
    client, _ = await swarm_client_factory({"SwarmHold": [("drone1", 0, "")]})

    results = await client.hold(["drone1"])

    assert results == [VehicleResult(vehicle="drone1", success=True, details="")]


async def test_return_to_home(swarm_client_factory):
    client, _ = await swarm_client_factory({"SwarmReturnToHome": [("drone1", 0, "")]})

    results = await client.return_to_home(["drone1"])

    assert results == [VehicleResult(vehicle="drone1", success=True, details="")]


async def test_stop_mission(swarm_client_factory):
    client, servicer = await swarm_client_factory(
        {"SwarmStopMission": [("drone1", 0, "")]}
    )

    results = await client.stop_mission(["drone1"])

    assert results == [VehicleResult(vehicle="drone1", success=True, details="")]
    # SwarmStopMissionRequest.request is typed as StopMissionResponse (not
    # StopMissionRequest) in the upstream swarm.proto -- an inconsistency
    # confirmed via protobuf descriptor introspection, not a bug in this code.
    sent = servicer.received["SwarmStopMission"][0]
    assert list(sent.vehicles) == ["drone1"]


async def test_set_velocity_sends_velocity_and_default_frame(swarm_client_factory):
    client, servicer = await swarm_client_factory(
        {"SwarmSetVelocityTarget": [("drone1", 0, "")]}
    )

    await client.set_velocity(
        ["drone1"], x_vel=1.0, y_vel=-2.0, z_vel=0.5, angular_vel=10.0
    )

    sent = servicer.received["SwarmSetVelocityTarget"][0]
    assert list(sent.vehicles) == ["drone1"]
    v = sent.request.velocity
    assert (v.x_vel, v.y_vel, v.z_vel, v.angular_vel) == pytest.approx(
        (1.0, -2.0, 0.5, 10.0)
    )
    # frame is intentionally left unset -> REFERENCE_FRAME_UNSPECIFIED, which
    # the driver defaults to BODY, matching the old Joystick's implicit frame.
    assert sent.request.frame == control_pb2.REFERENCE_FRAME_UNSPECIFIED


async def test_set_gimbal_pose_sends_offset_pose(swarm_client_factory):
    client, servicer = await swarm_client_factory(
        {"SwarmSetGimbalAngleTarget": [("drone1", 0, "")]}
    )

    await client.set_gimbal_pose(["drone1"], pitch=5.0, yaw=-10.0, roll=0.0)

    sent = servicer.received["SwarmSetGimbalAngleTarget"][0]
    assert sent.request.angle_mode == control_pb2.ANGLE_MODE_OFFSET
    p = sent.request.pose
    assert (p.pitch, p.yaw, p.roll) == pytest.approx((5.0, -10.0, 0.0))


async def test_upload_mission_sends_header_then_chunks(swarm_client_factory):
    client, servicer = await swarm_client_factory(
        {"SwarmUploadMission": [("drone1", 0, "")]}
    )
    amd = bytes(range(256)) * 2000  # 512000 bytes -> 2 chunks
    arm = b"\x01" * 10

    events = [
        e async for e in client.upload_mission(["drone1"], {"amd64": amd, "arm64": arm})
    ]

    assert events == [
        {"type": "result", "vehicle": "drone1", "success": True, "details": ""}
    ]
    requests = servicer.received["SwarmUploadMission"][0]
    header = requests[0].header
    assert list(header.vehicles) == ["drone1"]
    by_arch = {v.arch: v for v in header.variants}
    assert by_arch["amd64"].size == len(amd)
    assert by_arch["amd64"].sha256 == hashlib.sha256(amd).digest()
    assert by_arch["arm64"].size == len(arm)
    chunks = [r.chunk for r in requests[1:]]
    assert all(r.WhichOneof("part") == "chunk" for r in requests[1:])
    assert all(len(c.data) <= 256 * 1024 for c in chunks)
    assert b"".join(c.data for c in chunks if c.arch == "amd64") == amd
    assert b"".join(c.data for c in chunks if c.arch == "arm64") == arm


async def test_upload_mission_relays_progress_and_failures(swarm_client_factory):
    client, _ = await swarm_client_factory(
        {
            "SwarmUploadMission": [
                ("progress", "drone1", 0, 100),
                ("progress", "drone1", 100, 100),
                ("drone1", 0, ""),
                ("drone2", 9, "no arm64 variant provided"),
            ]
        }
    )

    events = [
        e async for e in client.upload_mission(["drone1", "drone2"], {"amd64": b"x"})
    ]

    assert events == [
        {"type": "progress", "vehicle": "drone1", "sent": 0, "total": 100},
        {"type": "progress", "vehicle": "drone1", "sent": 100, "total": 100},
        {"type": "result", "vehicle": "drone1", "success": True, "details": ""},
        {
            "type": "result",
            "vehicle": "drone2",
            "success": False,
            "details": "no arm64 variant provided",
        },
    ]


async def test_upload_mission_channel_failure(swarm_client_factory):
    client, _ = await swarm_client_factory(
        {"SwarmUploadMission": RuntimeError("swarm controller down")}
    )

    with pytest.raises(grpc.aio.AioRpcError):
        async for _ in client.upload_mission(["drone1"], {"amd64": b"x"}):
            pass
