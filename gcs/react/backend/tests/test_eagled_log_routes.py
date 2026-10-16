import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from app import eagled_log_routes
from app.daemon_backend import DaemonUnreachable, LogRecord, LogSource
from app.eagled_log_routes import (
    LogStreamBody,
    _sse_events,
    get_log_sources,
    stream_logs,
)


def _parse(event: str) -> tuple[str, dict]:
    lines = event.strip().split("\n")
    assert lines[0].startswith("event: ") and lines[1].startswith("data: "), event
    return lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])


class FakeLogBackend:
    """Scripted log methods; `failure` is raised by both instead."""

    def __init__(self, sources=(), records=(), failure=None, quiet_follow=False):
        self.sources, self.records, self.failure = list(sources), list(records), failure
        self.quiet_follow = quiet_follow
        self.requests = []
        self.stream_finished = asyncio.Event()

    async def list_log_sources(self):
        if self.failure:
            raise self.failure
        return self.sources

    async def stream_logs(self, sources, tail, follow, after_seq):
        self.requests.append((sources, tail, follow, after_seq))
        try:
            if self.failure:
                raise self.failure
            for record in self.records:
                yield record
            if follow and self.quiet_follow:
                await asyncio.Event().wait()
        finally:
            self.stream_finished.set()


@pytest.fixture
def fake_backend(monkeypatch):
    def install(backend):
        @asynccontextmanager
        async def open_backend(address):
            yield backend

        monkeypatch.setattr(eagled_log_routes, "open_backend", open_backend)
        return backend

    return install


async def test_log_sources_shapes_response(fake_backend):
    fake_backend(FakeLogBackend(sources=[LogSource("daemon", True, 42)]))

    result = await get_log_sources("x")

    assert result.reachable is True
    assert [s.model_dump() for s in result.sources] == [
        {"name": "daemon", "running": True, "size_bytes": 42}
    ]


async def test_log_sources_unreachable_is_reachable_false_not_an_error(fake_backend):
    fake_backend(FakeLogBackend(failure=DaemonUnreachable("boom")))

    result = await get_log_sources("x")

    assert result.reachable is False
    assert "boom" in result.error
    assert result.sources == []


async def test_log_sources_from_a_real_eagled_are_not_supported():
    # The revised proto has no log RPCs; GrpcDaemonBackend refuses without a call.
    result = await get_log_sources("127.0.0.1:1")
    assert (
        result.reachable is True
        and result.ok is False
        and "not supported" in result.error
    )


async def test_stream_relays_records_as_sse_and_forwards_request(fake_backend):
    backend = fake_backend(
        FakeLogBackend(
            records=[
                LogRecord(
                    "daemon",
                    4,
                    datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                    "info",
                    "four",
                    0,
                ),
                LogRecord("daemon", 0, None, "", "gap", 7),
            ]
        )
    )
    body = LogStreamBody(
        address="x", sources=["daemon"], tail=5, follow=False, after_seq={"daemon": 3}
    )

    parsed = [_parse(e) for e in [e async for e in _sse_events(body)]]

    assert [kind for kind, _ in parsed] == ["record", "record"]
    assert parsed[0][1] == {
        "source": "daemon",
        "seq": 4,
        "time": "1970-01-01T00:00:01Z",
        "level": "info",
        "text": "four",
        "dropped": 0,
    }
    assert parsed[1][1]["dropped"] == 7 and parsed[1][1]["seq"] == 0
    assert parsed[1][1]["time"] == "1970-01-01T00:00:00Z"
    assert backend.requests == [(["daemon"], 5, False, {"daemon": 3})]


async def test_stream_reports_unreachable_daemon_as_error_event(fake_backend):
    fake_backend(FakeLogBackend(failure=DaemonUnreachable("down")))

    events = [e async for e in _sse_events(LogStreamBody(address="x", follow=False))]

    assert len(events) == 1
    kind, data = _parse(events[0])
    assert kind == "error"
    assert data["reachable"] is False and "down" in data["error"]


async def test_quiet_stream_sends_keepalives_and_cancels_upstream_on_close(
    fake_backend,
):
    backend = fake_backend(FakeLogBackend(quiet_follow=True))
    gen = _sse_events(LogStreamBody(address="x", follow=True), keepalive_seconds=0.05)

    assert await gen.__anext__() == ": keepalive\n\n"
    assert await gen.__anext__() == ": keepalive\n\n"
    await gen.aclose()

    await asyncio.wait_for(backend.stream_finished.wait(), timeout=2)


async def test_stream_route_is_an_uncached_event_stream():
    resp = await stream_logs(LogStreamBody(address="127.0.0.1:1"))

    assert resp.media_type == "text/event-stream"
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"


async def test_log_sources_from_a_mock_daemon(mock_daemons):
    result = await get_log_sources("mock://lab-a")

    assert result.reachable is True and result.ok is True
    assert {s.name for s in result.sources} >= {
        "eagled",
        "harpy-driver",
        "harpy-mission",
        "detector",
        "swarm-controller",
    }


async def test_stream_from_a_mock_daemon_relays_backlog(mock_daemons):
    body = LogStreamBody(
        address="mock://lab-a", sources=["harpy"], tail=2, follow=False
    )

    parsed = [_parse(e) for e in [e async for e in _sse_events(body)]]

    assert [(kind, data["seq"]) for kind, data in parsed] == [
        ("record", 4),
        ("record", 5),
    ]
    assert parsed[0][1]["time"].endswith("Z")


async def test_log_sources_mock_disabled_is_unreachable():
    result = await get_log_sources("mock://lab-a")

    assert result.reachable is False and "disabled" in result.error
