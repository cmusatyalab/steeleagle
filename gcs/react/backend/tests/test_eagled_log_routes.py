import asyncio
import json

from google.protobuf.timestamp_pb2 import Timestamp
from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app.eagled_log_routes import (
    LogStreamBody,
    _sse_events,
    get_log_sources,
    stream_logs,
)
from tests.fake_eagled import daemon_server_factory  # noqa: F401 -- fixture


def _parse(event: str) -> tuple[str, dict]:
    lines = event.strip().split("\n")
    assert lines[0].startswith("event: ") and lines[1].startswith("data: "), event
    return lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])


async def test_log_sources_shapes_response(daemon_server_factory):  # noqa: F811
    resp = eagled_pb2.ListLogSourcesResponse(
        sources=[eagled_pb2.LogSource(name="daemon", running=True, size_bytes=42)]
    )
    _servicer, address = await daemon_server_factory({"ListLogSources": resp})

    result = await get_log_sources(address)

    assert result.reachable is True
    assert [s.model_dump() for s in result.sources] == [
        {"name": "daemon", "running": True, "size_bytes": 42}
    ]


async def test_log_sources_unreachable_is_reachable_false_not_an_error(
    daemon_server_factory,  # noqa: F811
):
    _servicer, address = await daemon_server_factory(
        {"ListLogSources": Exception("boom")}
    )

    result = await get_log_sources(address)

    assert result.reachable is False
    assert "boom" in result.error
    assert result.sources == []


async def test_stream_relays_records_as_sse_and_forwards_request(
    daemon_server_factory,  # noqa: F811
):
    records = [
        eagled_pb2.LogRecord(
            source="daemon", seq=4, time=Timestamp(seconds=1), level="info", text="four"
        ),
        eagled_pb2.LogRecord(source="daemon", seq=0, dropped=7, text="gap"),
    ]
    servicer, address = await daemon_server_factory({"StreamLogs": records})
    body = LogStreamBody(
        address=address,
        sources=["daemon"],
        tail=5,
        follow=False,
        after_seq={"daemon": 3},
    )

    events = [e async for e in _sse_events(body)]

    parsed = [_parse(e) for e in events]
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
    sent = servicer.received["StreamLogs"][0]
    assert list(sent.sources) == ["daemon"]
    assert sent.tail == 5 and sent.follow is False
    assert dict(sent.after_seq) == {"daemon": 3}


async def test_stream_reports_unreachable_daemon_as_error_event(
    daemon_server_factory,  # noqa: F811
):
    _servicer, address = await daemon_server_factory({"StreamLogs": Exception("down")})

    events = [
        e async for e in _sse_events(LogStreamBody(address=address, follow=False))
    ]

    assert len(events) == 1
    kind, data = _parse(events[0])
    assert kind == "error"
    assert data["reachable"] is False and "down" in data["error"]


async def test_quiet_stream_sends_keepalives_and_cancels_upstream_on_close(
    daemon_server_factory,  # noqa: F811
):
    servicer, address = await daemon_server_factory({"StreamLogs": []})
    gen = _sse_events(
        LogStreamBody(address=address, follow=True), keepalive_seconds=0.05
    )

    assert await gen.__anext__() == ": keepalive\n\n"
    assert await gen.__anext__() == ": keepalive\n\n"
    await gen.aclose()

    await asyncio.wait_for(servicer.stream_finished.wait(), timeout=2)


async def test_stream_route_is_an_uncached_event_stream():
    resp = await stream_logs(LogStreamBody(address="127.0.0.1:1"))

    assert resp.media_type == "text/event-stream"
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"
