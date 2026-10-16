"""FastAPI routes exposing eagled's log streaming (StreamLogs /
ListLogSources) to the GCS frontend -- see
docs/superpowers/specs/2026-09-21-eagled-log-streaming-design.md.
The routes reach eagled through open_backend (a mock:// or gRPC backend),
so the same handlers serve both.

Like eagled_routes.py, an unreachable daemon is an ordinary state, never a
500: log-sources returns `reachable: false`, and a stream that can't reach or
loses its daemon sends one `error` event and ends (HTTP status stays 200).
Request-validation failures (a negative tail, say) are the one exception:
FastAPI answers those with 422 before any daemon is contacted."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, NonNegativeInt

from app.daemon_backend import BackendFailure, DaemonUnreachable, LogRecord
from app.daemon_backends import open_backend

router = APIRouter(prefix="/api/daemons", tags=["daemons"])

KEEPALIVE_SECONDS = 15.0
_KEEPALIVE = ": keepalive\n\n"
_END = object()


class LogSourceModel(BaseModel):
    name: str
    running: bool
    size_bytes: int


class LogSourcesResponse(BaseModel):
    reachable: bool
    ok: bool = True
    sources: list[LogSourceModel] = []
    error: str | None = None


class LogStreamBody(BaseModel):
    address: str
    sources: list[str] = []
    tail: int = Field(default=0, ge=0, le=100_000)
    follow: bool = True
    after_seq: dict[str, NonNegativeInt] = {}


@router.get("/log-sources")
async def get_log_sources(address: str) -> LogSourcesResponse:
    try:
        async with open_backend(address) as backend:
            sources = await backend.list_log_sources()
    except BackendFailure as e:
        return LogSourcesResponse(
            reachable=not isinstance(e, DaemonUnreachable), ok=False, error=str(e)
        )
    return LogSourcesResponse(
        reachable=True,
        sources=[
            LogSourceModel(name=s.name, running=s.running, size_bytes=s.size_bytes)
            for s in sources
        ],
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _iso(time: datetime | None) -> str:
    # LogViewer parses `time` with `new Date`, and the pre-port backend sent
    # the epoch for unset timestamps (gap markers), so keep that wire value.
    if time is None:
        return "1970-01-01T00:00:00Z"
    return time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_json(record: LogRecord) -> dict:
    return {
        "source": record.source,
        "seq": record.seq,
        "time": _iso(record.time),
        "level": record.level,
        "text": record.text,
        "dropped": record.dropped,
    }


async def _next_or_end(records):
    try:
        return await records.__anext__()
    except StopAsyncIteration:
        return _END


async def _sse_events(
    body: LogStreamBody, keepalive_seconds: float = KEEPALIVE_SECONDS
):
    """Relays eagled's LogRecord stream as SSE strings. The pending read is
    never cancelled to emit a keepalive (that would tear down the gRPC
    stream); it is only cancelled when this generator is closed."""
    try:
        async with open_backend(body.address) as backend:
            records = backend.stream_logs(
                body.sources, body.tail, body.follow, dict(body.after_seq)
            )
            pending = None
            try:
                while True:
                    if pending is None:
                        pending = asyncio.ensure_future(_next_or_end(records))
                    done, _ = await asyncio.wait({pending}, timeout=keepalive_seconds)
                    if not done:
                        yield _KEEPALIVE
                        continue
                    item, pending = pending.result(), None
                    if item is _END:
                        return
                    yield _sse("record", _record_json(item))
            finally:
                if pending is not None:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                await records.aclose()
    except BackendFailure as e:
        yield _sse(
            "error",
            {"reachable": not isinstance(e, DaemonUnreachable), "error": str(e)},
        )


@router.post("/logs/stream")
async def stream_logs(body: LogStreamBody) -> StreamingResponse:
    return StreamingResponse(
        _sse_events(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
