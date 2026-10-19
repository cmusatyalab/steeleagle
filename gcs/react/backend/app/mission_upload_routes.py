"""Mission upload routes -- see
docs/superpowers/specs/2026-09-28-mission-upload-streaming-design.md.

Both routes stream NDJSON: `stage` lines, per-vehicle `progress` and
`result` lines relayed from the swarm controller, or a single terminal
`error` line. Input problems found before any gRPC call (no vehicles, bad
files) are ordinary HTTP 400s instead."""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

import grpc
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app import compiler_routes
from app.compiler_routes import CompileFailed, MissionGraph
from app.eaglec_client import EaglecFailure
from app.mission_binary import MAX_MISSION_SIZE, elf_arch
from app.swarm_client import SwarmClient

logger = logging.getLogger("rich")

router = APIRouter(tags=["missions"])

_swarm_client_provider: Callable[[], SwarmClient] | None = None


def setup(provider: Callable[[], SwarmClient]) -> None:
    """Called from api.py's lifespan: `provider` returns the active
    backend's SwarmClient (api.py owns backend selection)."""
    global _swarm_client_provider
    _swarm_client_provider = provider


def _current_swarm_client() -> SwarmClient:
    if _swarm_client_provider is None:
        raise HTTPException(status_code=503, detail="swarm client not initialized")
    return _swarm_client_provider()


def _require_vehicles(vehicles: list[str]) -> None:
    if not vehicles:
        raise HTTPException(status_code=400, detail="Select at least one vehicle")


def variants_from_files(files: list[tuple[str, bytes]]) -> dict[str, bytes]:
    """Maps uploaded (filename, bytes) pairs to {arch: bytes} using each
    file's ELF header; filenames are only used in error messages."""
    if not files:
        raise HTTPException(
            status_code=400, detail="Select at least one mission binary"
        )
    if len(files) > 2:
        raise HTTPException(
            status_code=400,
            detail="At most two mission binaries (one per architecture) can be uploaded at once",
        )
    variants: dict[str, bytes] = {}
    for name, data in files:
        if len(data) > MAX_MISSION_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"{name} is larger than the {MAX_MISSION_SIZE // (1024 * 1024)} MiB limit",
            )
        try:
            arch = elf_arch(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"{name}: {e}") from e
        if arch in variants:
            raise HTTPException(
                status_code=400,
                detail=f"Two files were built for {arch}; upload at most one per architecture",
            )
        variants[arch] = data
    return variants


async def upload_events(
    client: SwarmClient, vehicles: list[str], variants: dict[str, bytes]
) -> AsyncIterator[dict]:
    yield {"type": "stage", "stage": "uploading"}
    try:
        async for event in client.upload_mission(vehicles, variants):
            yield event
    except grpc.aio.AioRpcError as e:
        yield {
            "type": "error",
            "detail": f"Upload failed: {e.code().name} - {e.details()}",
        }
    except Exception as e:
        logger.exception("Unexpected error while uploading mission")
        yield {"type": "error", "detail": f"Upload failed: {e}"}


# Every arch a vehicle may run; the swarm controller picks each vehicle's.
DEPLOY_ARCHS = ("amd64", "arm64")


async def deploy_events(
    build: Callable[[], Awaitable[dict[str, bytes]]],
    swarm_client: SwarmClient,
    vehicles: list[str],
) -> AsyncIterator[dict]:
    """Runs build (every arch's binary, as {arch: bytes}), then uploads them
    all; compile errors end the stream before the swarm controller is
    contacted."""
    yield {"type": "stage", "stage": "building"}
    try:
        variants = await build()
    except CompileFailed as e:
        yield {
            "type": "error",
            "detail": "Build failed: " + "; ".join(err["message"] for err in e.errors),
            "errors": e.errors,
        }
        return
    except EaglecFailure as e:
        yield {
            "type": "error",
            "detail": f"Build failed: {compiler_routes.describe(e)}",
        }
        return
    except Exception as e:
        logger.exception("Unexpected error while building mission")
        yield {"type": "error", "detail": f"Build failed: {e}"}
        return
    if not variants:
        yield {"type": "error", "detail": "Build produced no binaries"}
        return
    async for event in upload_events(swarm_client, vehicles, variants):
        yield event


async def _ndjson(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for event in events:
        yield json.dumps(event) + "\n"


def _ndjson_response(events: AsyncIterator[dict]) -> StreamingResponse:
    return StreamingResponse(_ndjson(events), media_type="application/x-ndjson")


@router.post("/api/upload")
async def upload_route(
    files: list[UploadFile] = File(default=[]),
    vehicles: list[str] = Form(default=[]),
):
    _require_vehicles(vehicles)
    if len(files) > 2:
        raise HTTPException(
            status_code=400,
            detail="At most two mission binaries (one per architecture) can be uploaded at once",
        )
    variants = variants_from_files(
        [(f.filename or "file", await f.read(MAX_MISSION_SIZE + 1)) for f in files]
    )
    return _ndjson_response(upload_events(_current_swarm_client(), vehicles, variants))


class DeployRequest(MissionGraph):
    vehicles: list[str]


@router.post("/api/deploy")
async def deploy_route(request: DeployRequest):
    _require_vehicles(request.vehicles)
    swarm_client = _current_swarm_client()
    state = await compiler_routes.ready()
    return _ndjson_response(
        deploy_events(
            lambda: compiler_routes.compile_graph(state, request, DEPLOY_ARCHS),
            swarm_client,
            request.vehicles,
        )
    )
