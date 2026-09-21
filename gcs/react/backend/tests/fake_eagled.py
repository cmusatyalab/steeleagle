"""A fake DaemonService gRPC server for testing EagledClient and
eagled_routes' reachability handling against real (fake) network
behavior -- mirrors tests/test_swarm_client.py's FakeSwarmServicer
pattern. Unlike swarm's streaming RPCs, every DaemonService RPC in scope
is unary_unary, so _run just returns a single message instead of
yielding a stream."""

import grpc
import pytest
from steeleagle_protocol.v1.services.eagled import eagled_pb2, eagled_pb2_grpc


class FakeDaemonServicer(eagled_pb2_grpc.DaemonServiceServicer):
    """`script[rpc_name]` is either a response message to return, or an
    Exception instance whose message aborts the call with UNAVAILABLE.
    Every request received is recorded in self.received[rpc_name] so
    tests can assert on what was actually sent."""

    def __init__(self, script: dict):
        self._script = script
        self.received: dict[str, list] = {}

    async def _run(self, rpc_name, request, context):
        self.received.setdefault(rpc_name, []).append(request)
        outcome = self._script[rpc_name]
        if isinstance(outcome, Exception):
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(outcome))
        return outcome

    async def GetStatus(self, request, context):
        return await self._run("GetStatus", request, context)

    async def StopVehicles(self, request, context):
        return await self._run("StopVehicles", request, context)

    async def RestartVehicles(self, request, context):
        return await self._run("RestartVehicles", request, context)

    async def ForgetVehicles(self, request, context):
        return await self._run("ForgetVehicles", request, context)

    async def GetInstalledPlugins(self, request, context):
        return await self._run("GetInstalledPlugins", request, context)

    async def RestartDaemon(self, request, context):
        return await self._run("RestartDaemon", request, context)

    async def ResetConfig(self, request, context):
        return await self._run("ResetConfig", request, context)


@pytest.fixture
async def daemon_server_factory():
    """Yields an async factory `_make(script) -> (FakeDaemonServicer,
    address)` that starts a real grpc.aio server on a random loopback
    port for each call. All servers started this way are stopped when
    the test finishes."""
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


class FakeEagledClient:
    """Duck-types EagledClient's public methods for testing
    eagled_routes' response-shaping functions without a live gRPC
    server -- mirrors tests/fake_dslcompiler.py's FakeDslCompilerClient
    pattern. Construct with canned return values for whichever methods a
    test exercises; calling a method with no canned value raises
    AssertionError so an unexpected call fails loudly."""

    def __init__(
        self,
        status: eagled_pb2.GetStatusResponse | None = None,
        stop_vehicles: eagled_pb2.StopVehiclesResponse | None = None,
        restart_vehicles: eagled_pb2.RestartVehiclesResponse | None = None,
        forget_vehicles: eagled_pb2.ForgetVehiclesResponse | None = None,
        installed_plugins: eagled_pb2.GetInstalledPluginsResponse | None = None,
    ) -> None:
        self._status = status
        self._stop_vehicles = stop_vehicles
        self._restart_vehicles = restart_vehicles
        self._forget_vehicles = forget_vehicles
        self._installed_plugins = installed_plugins
        self.stop_vehicles_calls: list[list[str]] = []
        self.restart_vehicles_calls: list[list[str]] = []
        self.forget_vehicles_calls: list[list[str]] = []

    async def get_status(self):
        assert self._status is not None, "FakeEagledClient: no status configured"
        return self._status

    async def stop_vehicles(self, names: list[str]):
        assert self._stop_vehicles is not None, (
            "FakeEagledClient: no stop_vehicles configured"
        )
        self.stop_vehicles_calls.append(names)
        return self._stop_vehicles

    async def restart_vehicles(self, names: list[str]):
        assert self._restart_vehicles is not None, (
            "FakeEagledClient: no restart_vehicles configured"
        )
        self.restart_vehicles_calls.append(names)
        return self._restart_vehicles

    async def forget_vehicles(self, names: list[str]):
        assert self._forget_vehicles is not None, (
            "FakeEagledClient: no forget_vehicles configured"
        )
        self.forget_vehicles_calls.append(names)
        return self._forget_vehicles

    async def get_installed_plugins(self):
        assert self._installed_plugins is not None, (
            "FakeEagledClient: no installed_plugins configured"
        )
        return self._installed_plugins

    async def restart_daemon(self):
        return eagled_pb2.RestartDaemonResponse()

    async def reset_config(self):
        return eagled_pb2.ResetConfigResponse()
