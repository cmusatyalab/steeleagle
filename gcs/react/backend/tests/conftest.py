"""Shared fixtures. `mock_daemons` turns on mock:// daemons (normally gated
by config.toml's [eagled] mock_enabled) with the artificial configure and
log-follow delays removed, and resets the registry afterwards so mock
state never leaks between tests. `daemon_server_factory` (a fake eagled
gRPC server) is registered here so test modules don't import it."""

import pytest

from app import daemon_registry
from tests.fake_eagled import daemon_server_factory  # noqa: F401 -- fixture


@pytest.fixture
def mock_daemons(monkeypatch):
    monkeypatch.setattr(daemon_registry, "MOCK_CONFIGURE_DELAY", 0)
    monkeypatch.setattr(daemon_registry, "MOCK_FOLLOW_INTERVAL", 0.01)
    daemon_registry.setup({"mock_enabled": True})
    yield daemon_registry
    daemon_registry.setup(None)
