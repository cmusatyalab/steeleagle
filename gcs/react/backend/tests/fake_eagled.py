"""A fake revised-proto DaemonService gRPC server, for testing
GrpcDaemonBackend and the routes' gRPC path against real (fake) network
behavior -- mirrors tests/test_swarm_client.py's FakeSwarmServicer
pattern."""

import grpc
import pytest
from steeleagle_protocol.v1.services.eagled import eagled_pb2_grpc


async def _maybe_abort(outcome, context) -> None:
    if isinstance(outcome, Exception):
        await context.abort(grpc.StatusCode.UNAVAILABLE, str(outcome))
    if (
        isinstance(outcome, tuple)
        and outcome
        and isinstance(outcome[0], grpc.StatusCode)
    ):
        await context.abort(outcome[0], outcome[1])


class FakeDaemonServicer(eagled_pb2_grpc.DaemonServiceServicer):
    """`script[rpc_name]` is a response message, an Exception (abort UNAVAILABLE), or a
    (grpc.StatusCode, details) tuple (abort with that code). Every request
    is recorded in self.received[rpc_name]."""

    def __init__(self, script: dict):
        self._script = script
        self.received: dict[str, list] = {}
        self.time_remaining: dict[str, float | None] = {}

    async def _run(self, rpc_name, request, context):
        self.received.setdefault(rpc_name, []).append(request)
        self.time_remaining[rpc_name] = context.time_remaining()
        outcome = self._script[rpc_name]
        await _maybe_abort(outcome, context)
        return outcome

    async def Configure(self, request, context):
        return await self._run("Configure", request, context)

    async def GetConfiguration(self, request, context):
        return await self._run("GetConfiguration", request, context)

    async def ResetConfiguration(self, request, context):
        return await self._run("ResetConfiguration", request, context)

    async def RestartServices(self, request, context):
        return await self._run("RestartServices", request, context)

    async def InstallPlugin(self, request, context):
        return await self._run("InstallPlugin", request, context)

    async def RemovePlugin(self, request, context):
        return await self._run("RemovePlugin", request, context)


@pytest.fixture
async def daemon_server_factory():
    """Yields `_make(script) -> (FakeDaemonServicer, address)`; each call
    starts a real grpc.aio server on a random loopback port, all stopped
    when the test finishes."""
    servers = []

    async def _make(script: dict):
        servicer = FakeDaemonServicer(script)
        server = grpc.aio.server()
        eagled_pb2_grpc.add_DaemonServiceServicer_to_server(servicer, server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        servers.append(server)
        return servicer, f"127.0.0.1:{port}"

    yield _make

    for server in servers:
        await server.stop(None)
