"""DaemonBackend over eagled's revised DaemonService gRPC API
(api/steeleagle_protocol/v1/services/daemon/daemon.proto, commit cddca5ff).

This owns a short-lived channel per use (eagled addresses are added and
removed at runtime by the frontend, so there is no fixed address to connect
at startup). The proto no longer carries logs (they are moving to logdy),
so the log methods raise NotSupported without making a call."""

from collections.abc import AsyncIterator

import grpc
from steeleagle_protocol.v1.services.daemon import daemon_pb2, daemon_pb2_grpc

from app.daemon_backend import (
    BackendFailure,
    DaemonError,
    DaemonUnreachable,
    LogRecord,
    LogSource,
    NotSupported,
    ServiceRef,
    ServiceState,
)

DEFAULT_TIMEOUT = 5.0
# Configure restarts the daemon and every service it runs (and may install
# plugins first when auto-install is on); restarting services waits on
# eagled's own stop timeout. Both get generous headroom.
CONFIGURE_TIMEOUT = 600.0
RESTART_TIMEOUT = 35.0

_CATEGORY_TO_PROTO = {
    "vehicle": daemon_pb2.SERVICE_CATEGORY_VEHICLE,
    "engine": daemon_pb2.SERVICE_CATEGORY_ENGINE,
    "monitor": daemon_pb2.SERVICE_CATEGORY_MONITOR,
    "commander": daemon_pb2.SERVICE_CATEGORY_COMMANDER,
    "simulator": daemon_pb2.SERVICE_CATEGORY_SIMULATOR,
    "database": daemon_pb2.SERVICE_CATEGORY_DATABASE,
    "extra": daemon_pb2.SERVICE_CATEGORY_EXTRA,
}

_CATEGORY_FROM_PROTO = {v: k for k, v in _CATEGORY_TO_PROTO.items()}


def _translate(rpc: str, e: grpc.aio.AioRpcError) -> BackendFailure:
    code = e.code()
    details = e.details() or code.name
    if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
        return DaemonUnreachable(details)
    if code == grpc.StatusCode.UNIMPLEMENTED:
        return NotSupported(rpc)
    return DaemonError(details)


class GrpcDaemonBackend:
    def __init__(
        self,
        address: str,
        timeout: float = DEFAULT_TIMEOUT,
        configure_timeout: float = CONFIGURE_TIMEOUT,
        restart_timeout: float = RESTART_TIMEOUT,
    ) -> None:
        self._address = address
        self._timeout = timeout
        self._configure_timeout = configure_timeout
        self._restart_timeout = restart_timeout
        self._channel: grpc.aio.Channel | None = None
        self._stub: daemon_pb2_grpc.DaemonServiceStub | None = None

    async def __aenter__(self) -> "GrpcDaemonBackend":
        self._channel = grpc.aio.insecure_channel(self._address)
        self._stub = daemon_pb2_grpc.DaemonServiceStub(self._channel)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._channel.close()

    async def _unary(self, rpc: str, request, timeout: float):
        try:
            return await getattr(self._stub, rpc)(request, timeout=timeout)
        except grpc.aio.AioRpcError as e:
            raise _translate(rpc, e) from e

    async def get_configuration(self) -> str:
        resp = await self._unary(
            "GetConfiguration", daemon_pb2.GetConfigurationRequest(), self._timeout
        )
        try:
            return resp.config_toml.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DaemonError(f"daemon config is not UTF-8: {e}") from e

    async def configure(self, config_toml: str) -> None:
        await self._unary(
            "Configure",
            daemon_pb2.ConfigureRequest(config_toml=config_toml),
            self._configure_timeout,
        )

    async def reset_configuration(self) -> None:
        await self._unary(
            "ResetConfiguration",
            daemon_pb2.ResetConfigurationRequest(),
            self._configure_timeout,
        )

    async def restart_services(self, refs: list[ServiceRef]) -> None:
        request = daemon_pb2.RestartServicesRequest(
            services=[
                daemon_pb2.ServiceRequest(
                    name=ref.name, category=_CATEGORY_TO_PROTO[ref.category]
                )
                for ref in refs
            ]
        )
        await self._unary("RestartServices", request, self._restart_timeout)

    async def list_services(self) -> list[ServiceState]:
        resp = await self._unary(
            "ListServices", daemon_pb2.ListServicesRequest(), self._timeout
        )
        # A category this GCS doesn't know (or UNSPECIFIED) has nowhere to
        # show on the Services tab, so it is left out.
        return [
            ServiceState(
                name=s.name,
                category=_CATEGORY_FROM_PROTO[s.category],
                running=s.running,
                uptime_s=s.uptime.ToTimedelta().total_seconds()
                if s.HasField("uptime")
                else None,
            )
            for s in resp.services
            if s.category in _CATEGORY_FROM_PROTO
        ]

    async def get_plugin_tomls(self) -> dict[str, bytes]:
        # Raw bytes: the catalog decodes each one, so a bad file is that
        # service's problem rather than the whole call's.
        resp = await self._unary(
            "GetConfiguration", daemon_pb2.GetConfigurationRequest(), self._timeout
        )
        return dict(resp.plugin_tomls)

    async def list_log_sources(self) -> list[LogSource]:
        raise NotSupported("ListLogSources")

    async def stream_logs(
        self, sources: list[str], tail: int, follow: bool, after_seq: dict[str, int]
    ) -> AsyncIterator[LogRecord]:
        raise NotSupported("StreamLogs")
        yield  # pragma: no cover -- makes this an async generator
