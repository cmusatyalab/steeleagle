"""The seam between eagled_routes and an eagled instance -- see
docs/superpowers/specs/2026-10-15-gcs-generic-plugins-design.md.

The methods mirror the revised DaemonService RPCs
(api/steeleagle_protocol/v1/services/eagled/eagled.proto), plus log
methods that the proto no longer has (logs are moving to logdy; until then
only the mock serves them). Two implementations: MockDaemonBackend
(app/mock_daemon.py) for `mock://` addresses while the eagled rework is in
progress, and GrpcDaemonBackend (app/grpc_daemon_backend.py) for real
daemons. Backends raise the BackendFailure subclasses below instead of
transport-specific errors, so routes handle both the same way."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class BackendFailure(Exception):
    pass


class DaemonUnreachable(BackendFailure):
    """The daemon couldn't be reached at all -- an ordinary state for the
    Orchestrate page, reported as `reachable: false`."""


class NotSupported(BackendFailure):
    def __init__(self, rpc: str):
        super().__init__(f"not supported by this eagled yet: {rpc}")
        self.rpc = rpc


class DaemonError(BackendFailure):
    """The daemon was reached but refused or failed the operation."""


@dataclass(frozen=True)
class ServiceRef:
    name: str
    category: str


@dataclass
class LogSource:
    name: str
    running: bool
    size_bytes: int


@dataclass
class LogRecord:
    source: str
    seq: int
    time: datetime | None
    level: str
    text: str
    dropped: int


class DaemonBackend(Protocol):
    async def get_configuration(self) -> str: ...
    async def configure(self, config_toml: str) -> None: ...
    async def reset_configuration(self) -> None: ...
    async def restart_services(self, refs: list[ServiceRef]) -> None: ...
    async def list_log_sources(self) -> list[LogSource]: ...
    def stream_logs(
        self, sources: list[str], tail: int, follow: bool, after_seq: dict[str, int]
    ) -> AsyncIterator[LogRecord]: ...
