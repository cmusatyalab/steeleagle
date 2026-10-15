"""FastAPI routes for the Plan page's FSM builder, backed by eaglec -- see
docs/superpowers/specs/2026-10-14-gcs-eaglec-compiler-integration-design.md.
Replaces dslcompiler_routes.py with the same request and response shapes,
plus /api/render_dsl."""

import asyncio
import contextlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.compiler_config import CompilerConfig, ensure_eaglec, load_compiler_config
from app.eaglec_client import EaglecClient, EaglecCompileErrors, EaglecFailure
from app.mission_translate import (
    TypeIndex,
    ast_to_dsl,
    ast_to_graph,
    graph_to_ast,
    prepare_geojson,
    registry_to_schema,
    upgrade_legacy_dsl,
)

logger = logging.getLogger("rich")

router = APIRouter(tags=["compiler"])


@dataclass(frozen=True)
class CompilerState:
    config: CompilerConfig
    client: EaglecClient
    index: TypeIndex
    schema: dict  # the /api/schema body


_state: CompilerState | None = None
_setup_error: str | None = None
_setup_task: asyncio.Task | None = None


def start(section: dict | None) -> None:
    """Called from api.py's lifespan. Resolves config, builds eaglec if
    needed and loads the schema in the background, so a cold Go cache
    doesn't hold up startup; routes wait for it."""
    global _setup_task
    _setup_task = asyncio.create_task(_setup(section))


async def stop() -> None:
    if _setup_task is not None and not _setup_task.done():
        _setup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _setup_task


async def _setup(section: dict | None) -> None:
    global _state, _setup_error
    try:
        config = load_compiler_config(section)
        await ensure_eaglec(config)
        _state = await load_state(config, EaglecClient(config.eaglec, config.timeout_s))
        _setup_error = None
        logger.info(
            f"FSM compiler ready: {len(_state.schema['actions'])} actions, "
            f"{len(_state.schema['events'])} events"
        )
    except Exception as e:
        _setup_error = describe(e)
        logger.error(f"FSM compiler unavailable: {_setup_error}")


async def load_state(config: CompilerConfig, client) -> CompilerState:
    index = TypeIndex(await client.schema(config.header()))
    schema = registry_to_schema(index)
    schema["imports"] = [{"path": i.path, "alias": i.alias} for i in config.imports]
    return CompilerState(config, client, index, schema)


def describe(e: Exception) -> str:
    if isinstance(e, EaglecFailure) and e.stderr:
        return f"{e}\n{e.stderr[-2000:]}"
    return str(e)


async def ready() -> CompilerState:
    """The loaded compiler state, waiting for startup to finish. 503 if it
    failed."""
    if _setup_task is not None and not _setup_task.done():
        await asyncio.shield(_setup_task)
    if _state is None:
        raise HTTPException(
            status_code=503,
            detail=f"FSM compiler unavailable: {_setup_error or 'not started'}",
        )
    return _state


class GraphNode(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class GraphEvent(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class GraphEdge(BaseModel):
    source: str
    event_id: str
    target: str


class MissionGraph(BaseModel):
    nodes: list[GraphNode]
    events: list[GraphEvent] = []
    edges: list[GraphEdge] = []
    start_id: str | None = None
    geojson: str = ""  # the Map tab's drawn features; "" means none


class BuildRequest(MissionGraph):
    arch: Literal["amd64", "arm64"]


class ParseDslRequest(BaseModel):
    dsl: str


class CompileFailed(Exception):
    """The mission didn't compile. errors are in the frontend's
    {node_id, event_id, message} shape."""

    def __init__(self, errors: list[dict]) -> None:
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


def _error(
    message: str, node_id: str | None = None, event_id: str | None = None
) -> dict:
    return {"node_id": node_id, "event_id": event_id, "message": message}


_NAME_RULE = (
    "can only contain letters, digits and underscores, and can't start with a digit"
)


def structural_errors(graph: MissionGraph) -> list[dict]:
    """Graph problems caught before compiling: duplicate ids, a missing or
    dangling start state, dangling edges."""
    errors = []
    seen: set[str] = set()
    for node in graph.nodes:
        if node.instance_id in seen:
            errors.append(
                _error(
                    f"Duplicate node instance_id: '{node.instance_id}'",
                    node.instance_id,
                )
            )
        seen.add(node.instance_id)
        if not node.instance_id.isidentifier():
            errors.append(
                _error(
                    f"Node name '{node.instance_id}' {_NAME_RULE}",
                    node.instance_id,
                )
            )
    seen_events: set[str] = set()
    for event in graph.events:
        if event.instance_id in seen_events:
            errors.append(
                _error(
                    f"Duplicate event instance_id: '{event.instance_id}'",
                    event_id=event.instance_id,
                )
            )
        seen_events.add(event.instance_id)
        if event.instance_id == "done":
            errors.append(
                _error(
                    "Event name 'done' is reserved for the action-finished transition",
                    event_id="done",
                )
            )
        elif not event.instance_id.isidentifier():
            errors.append(
                _error(
                    f"Event name '{event.instance_id}' {_NAME_RULE}",
                    event_id=event.instance_id,
                )
            )

    node_ids = {n.instance_id for n in graph.nodes}
    if graph.start_id is None:
        errors.append(
            _error("No start state: right-click a node and set it as the start state")
        )
    elif graph.start_id not in node_ids:
        errors.append(
            _error(
                f"start_id '{graph.start_id}' does not refer to any node",
                graph.start_id,
            )
        )

    event_ids = {e.instance_id for e in graph.events} | {"done"}
    for edge in graph.edges:
        if edge.source not in node_ids:
            errors.append(
                _error(
                    f"Edge source '{edge.source}' does not refer to any node",
                    edge.source,
                )
            )
        if edge.target not in node_ids:
            errors.append(
                _error(
                    f"Edge target '{edge.target}' does not refer to any node",
                    edge.target,
                )
            )
        if edge.event_id not in event_ids:
            errors.append(
                _error(
                    f"Edge event_id '{edge.event_id}' does not refer to any declared event",
                    event_id=edge.event_id,
                )
            )
    return errors


def map_errors(errors: list[dict], graph: MissionGraph) -> list[dict]:
    """eaglec errors in the frontend's shape: an error on a decl names the
    node or event with that instance_id."""
    node_ids = {n.instance_id for n in graph.nodes}
    event_ids = {e.instance_id for e in graph.events}
    return [
        {
            "node_id": e["decl"] if e["decl"] in node_ids else None,
            "event_id": e["decl"] if e["decl"] in event_ids else None,
            "message": e["message"],
        }
        for e in errors
    ]


async def compile_graph(
    state: CompilerState, graph: MissionGraph, archs: Iterable[str]
) -> dict[str, bytes]:
    """Compiles graph for every arch in parallel, returning {arch: binary}.
    Raises CompileFailed for anything wrong with the mission, EaglecFailure
    if eaglec itself failed."""
    errors = structural_errors(graph)
    geojson, feature_errors = prepare_geojson(graph.geojson)
    errors += [_error(m) for m in feature_errors]
    if errors:
        raise CompileFailed(errors)
    try:
        ast = graph_to_ast(graph.model_dump(), state.index, state.config.header())
    except ValueError as e:
        raise CompileFailed([_error(str(e))]) from e
    archs = list(archs)
    results = await asyncio.gather(
        *(state.client.compile(ast, geojson, arch) for arch in archs),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException) and not isinstance(
            result, EaglecCompileErrors
        ):
            raise result
    compile_errors: list[dict] = []
    for result in results:
        if isinstance(result, EaglecCompileErrors):
            # every arch reports the same link errors, so keep one of each
            for e in map_errors(result.errors, graph):
                if e not in compile_errors:
                    compile_errors.append(e)
    if compile_errors:
        raise CompileFailed(compile_errors)
    return dict(zip(archs, results))


@router.get("/api/schema")
async def get_schema(refresh: bool = False) -> dict:
    global _state
    state = await ready()
    if refresh:
        try:
            _state = state = await load_state(state.config, state.client)
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Reloading the schema failed: {describe(e)}"
            ) from e
    return state.schema


@router.post("/api/compile")
async def compile_route(graph: MissionGraph) -> dict:
    state = await ready()
    try:
        await compile_graph(state, graph, ["amd64"])
    except CompileFailed as e:
        return {"errors": e.errors}
    except EaglecFailure as e:
        raise HTTPException(status_code=500, detail=describe(e)) from e
    return {"ok": True}


@router.post("/api/render_dsl")
async def render_dsl_route(graph: MissionGraph) -> dict:
    state = await ready()
    try:
        ast = graph_to_ast(graph.model_dump(), state.index, state.config.header())
        return {"dsl": ast_to_dsl(ast)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/api/parse_dsl")
async def parse_dsl_route(request: ParseDslRequest) -> dict:
    state = await ready()
    dsl, warnings = upgrade_legacy_dsl(request.dsl)
    try:
        ast = await state.client.parse(dsl)
    except EaglecCompileErrors as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except EaglecFailure as e:
        raise HTTPException(status_code=500, detail=describe(e)) from e
    graph = ast_to_graph(ast, state.index)
    graph["warnings"] = warnings + graph["warnings"]
    configured = {i.path for i in state.config.imports}
    extra = [i["path"] for i in graph["imports"] if i["path"] not in configured]
    if extra:
        graph["warnings"].append(
            "Imports not in the GCS configuration are ignored when compiling: "
            + ", ".join(extra)
        )
    return graph


@router.post("/api/build")
async def build_route(request: BuildRequest) -> Response:
    state = await ready()
    try:
        binaries = await compile_graph(state, request, [request.arch])
    except CompileFailed as e:
        raise HTTPException(
            status_code=422,
            detail=f"Build failed for {request.arch}: "
            + "; ".join(err["message"] for err in e.errors),
        ) from e
    except EaglecFailure as e:
        raise HTTPException(status_code=500, detail=describe(e)) from e
    return Response(
        content=binaries[request.arch],
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="mission-{request.arch}"'
        },
    )
