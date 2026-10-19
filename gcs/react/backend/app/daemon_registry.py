"""Which DaemonBackend serves a given daemon address -- see
docs/superpowers/specs/2026-10-15-gcs-generic-plugins-design.md.

`mock://<name>` addresses get a MockDaemonBackend (one per address, kept
for the life of the process so edits stick between requests), but only
when config.toml's [eagled] mock_enabled is true; anything else is a real
eagled reached over gRPC."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from app.daemon_backend import DaemonBackend, DaemonUnreachable
from app.grpc_daemon_backend import GrpcDaemonBackend
from app.mock_daemon import MockDaemonBackend

MOCK_PREFIX = "mock://"
MOCK_DISCOVERED = [("lab-a (mock)", "mock://lab-a"), ("lab-b (mock)", "mock://lab-b")]
SEED_PATH = Path(__file__).with_name("mock_daemon_seed.toml")
MOCK_PLUGINS_DIR = Path(__file__).with_name("mock_plugins")
MOCK_CONFIGURE_DELAY = 1.5
MOCK_FOLLOW_INTERVAL = 2.0

_mock_enabled = False
_mocks: dict[str, MockDaemonBackend] = {}


def setup(eagled_cfg: dict | None) -> None:
    """Called from api.py's lifespan with config.toml's [eagled] table."""
    global _mock_enabled
    _mock_enabled = bool((eagled_cfg or {}).get("mock_enabled", False))
    _mocks.clear()


def mock_enabled() -> bool:
    return _mock_enabled


def _mock_for(address: str) -> MockDaemonBackend:
    if address not in _mocks:
        _mocks[address] = MockDaemonBackend(
            address,
            SEED_PATH.read_text(),
            configure_delay=MOCK_CONFIGURE_DELAY,
            follow_interval=MOCK_FOLLOW_INTERVAL,
            plugin_dir=MOCK_PLUGINS_DIR,
        )
    return _mocks[address]


@asynccontextmanager
async def open_backend(address: str) -> AsyncIterator[DaemonBackend]:
    if address.startswith(MOCK_PREFIX):
        if not _mock_enabled:
            raise DaemonUnreachable(
                "mock daemons are disabled (set [eagled] mock_enabled = true in config.toml)"
            )
        yield _mock_for(address)
        return
    async with GrpcDaemonBackend(address) as backend:
        yield backend
