"""FastAPI routes exposing eagled's log streaming (StreamLogs /
ListLogSources) to the GCS frontend -- see
docs/superpowers/specs/2026-09-21-eagled-log-streaming-design.md.

Like eagled_routes.py, an unreachable daemon is an ordinary state, never a
500: log-sources returns `reachable: false`, and a stream that can't reach or
loses its daemon sends one `error` event and ends (HTTP status stays 200).
Request-validation failures (a negative tail, say) are the one exception:
FastAPI answers those with 422 before any daemon is contacted."""

import asyncio
import json

import grpc
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, NonNegativeInt
from steeleagle_protocol.v1.services.eagled import eagled_pb2

from app.eagled_client import EagledClient

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
        async with EagledClient(address) as client:
            resp = await client.list_log_sources()
    except grpc.aio.AioRpcError as e:
        return LogSourcesResponse(reachable=False, error=e.details() or e.code().name)
    return LogSourcesResponse(
        reachable=True,
        sources=[
            LogSourceModel(name=s.name, running=s.running, size_bytes=s.size_bytes)
            for s in resp.sources
        ],
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _record_json(record: eagled_pb2.LogRecord) -> dict:
    return {
        "source": record.source,
        "seq": record.seq,
        "time": record.time.ToJsonString(),
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
        async with EagledClient(body.address) as client:
            records = client.stream_logs(
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
    except grpc.aio.AioRpcError as e:
        yield _sse("error", {"reachable": False, "error": e.details() or e.code().name})


@router.post("/logs/stream")
async def stream_logs(body: LogStreamBody) -> StreamingResponse:
    return StreamingResponse(
        _sse_events(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
