"""Thin wrapper over DaemonServiceStub: one typed method per RPC this GCS
wires up (see docs/superpowers/specs/2026-09-18-orchestration-eagled-wiring-design.md
for which RPCs and why), mirroring app/swarm_client.py's and
app/dslcompiler_client.py's pattern -- with one deliberate difference.
Those wrap a channel opened once at app startup against one address
fixed in config.toml. eagled addresses are neither fixed nor known at
startup -- they're arbitrary host:port strings a user adds/removes at
runtime via the frontend. So this owns a short-lived channel per
instance instead, opened/closed via async context manager, mirroring
eagle CLI's own connect-call-disconnect-per-invocation lifecycle
(cmd/eagle/main.go: grpc.NewClient with insecure creds, no persistent
connection, no auth -- eagled has none today)."""

import grpc
from steeleagle_protocol.v1.services.eagled import eagled_pb2, eagled_pb2_grpc

DEFAULT_TIMEOUT = 5.0

# StopVehicles/RestartVehicles/ForgetVehicles/ResetConfig all funnel through
# eagled's stopOne, which eagled itself bounds at StopTimeout = 30s per
# vehicle (cmd/eagled/daemon.go:53) -- RestartVehicles additionally waits on
# startVehicles, which can block on TailscaleStartTimeout = 30s
# (daemon.go:57) if vehicle-level tsnet is enabled. DEFAULT_TIMEOUT is far
# too short for any of these four calls; this comfortably exceeds eagled's
# own worst-case bound plus network/gRPC overhead. GetStatus,
# GetInstalledPlugins, and RestartDaemon don't touch vehicle-stop at all, so
# they stay on DEFAULT_TIMEOUT.
VEHICLE_LIFECYCLE_TIMEOUT = 35.0


class EagledClient:
    def __init__(
        self,
        address: str,
        timeout: float = DEFAULT_TIMEOUT,
        vehicle_lifecycle_timeout: float = VEHICLE_LIFECYCLE_TIMEOUT,
    ) -> None:
        self._address = address
        self._timeout = timeout
        self._vehicle_lifecycle_timeout = vehicle_lifecycle_timeout
        self._channel: grpc.aio.Channel | None = None
        self._stub: eagled_pb2_grpc.DaemonServiceStub | None = None

    async def __aenter__(self) -> "EagledClient":
        self._channel = grpc.aio.insecure_channel(self._address)
        self._stub = eagled_pb2_grpc.DaemonServiceStub(self._channel)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._channel.close()

    async def get_status(self) -> eagled_pb2.GetStatusResponse:
        return await self._stub.GetStatus(
            eagled_pb2.GetStatusRequest(), timeout=self._timeout
        )

    async def stop_vehicles(self, names: list[str]) -> eagled_pb2.StopVehiclesResponse:
        return await self._stub.StopVehicles(
            eagled_pb2.StopVehiclesRequest(names=names),
            timeout=self._vehicle_lifecycle_timeout,
        )

    async def restart_vehicles(
        self, names: list[str]
    ) -> eagled_pb2.RestartVehiclesResponse:
        return await self._stub.RestartVehicles(
            eagled_pb2.RestartVehiclesRequest(names=names),
            timeout=self._vehicle_lifecycle_timeout,
        )

    async def forget_vehicles(
        self, names: list[str]
    ) -> eagled_pb2.ForgetVehiclesResponse:
        return await self._stub.ForgetVehicles(
            eagled_pb2.ForgetVehiclesRequest(names=names),
            timeout=self._vehicle_lifecycle_timeout,
        )

    async def get_installed_plugins(
        self,
    ) -> eagled_pb2.GetInstalledPluginsResponse:
        return await self._stub.GetInstalledPlugins(
            eagled_pb2.GetInstalledPluginsRequest(), timeout=self._timeout
        )

    async def restart_daemon(self) -> eagled_pb2.RestartDaemonResponse:
        return await self._stub.RestartDaemon(
            eagled_pb2.RestartDaemonRequest(), timeout=self._timeout
        )

    async def reset_config(self) -> eagled_pb2.ResetConfigResponse:
        return await self._stub.ResetConfig(
            eagled_pb2.ResetConfigRequest(), timeout=self._vehicle_lifecycle_timeout
        )
