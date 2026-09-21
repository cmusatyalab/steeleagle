"""FastAPI routes for the DSL-compiler service -- extracted from
api.py's original monolithic route list (see
docs/superpowers/specs/2026-09-18-orchestration-eagled-wiring-design.md,
"DSL-compiler route extraction") as a clean, self-contained move: this
file owns its own channel/client lifecycle rather than sharing
api.py's, since nothing outside these 4 routes ever touched
dslcompiler_channel/dslcompiler_client."""

import logging
from typing import Literal

import grpc
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from steeleagle_protocol.v1.services.dslcompiler import (
    dslcompiler_pb2,
    dslcompiler_pb2_grpc,
)

from app.dslcompiler_client import DslCompilerClient

logger = logging.getLogger("rich")

router = APIRouter(tags=["dslcompiler"])

_channel: grpc.aio.Channel | None = None
_client: DslCompilerClient | None = None


def setup(dsl_cfg: dict | None) -> None:
    """Called from api.py's lifespan on startup. Opens the
    DslCompilerService channel if [dslcompiler] is configured; routes
    return 503 via _current_dslcompiler_client() until this has run."""
    global _channel, _client
    if dsl_cfg and dsl_cfg.get("controller"):
        _channel = grpc.aio.insecure_channel(dsl_cfg["controller"])
        stub = dslcompiler_pb2_grpc.DslCompilerServiceStub(_channel)
        _client = DslCompilerClient(stub)
        logger.info(
            f"Opened DslCompilerService stub at GRPC endpoint: {dsl_cfg['controller']}"
        )
    else:
        logger.warning(
            "no [dslcompiler] config section (or no 'controller' key) — "
            "FSM-builder routes will return 503 until config.toml is updated"
        )


async def teardown() -> None:
    """Called from api.py's lifespan on shutdown."""
    if _channel is not None:
        await _channel.close()


def _current_dslcompiler_client() -> DslCompilerClient:
    if _client is None:
        raise HTTPException(
            status_code=503, detail="dslcompiler client not initialized"
        )
    return _client


def _field_value_to_python(fv: dslcompiler_pb2.FieldValue):
    which = fv.WhichOneof("value")
    if which == "float_value":
        return fv.float_value
    if which == "int_value":
        return fv.int_value
    if which == "string_value":
        return fv.string_value
    if which == "bool_value":
        return fv.bool_value
    if which == "ident_ref":
        return fv.ident_ref
    if which == "array_value":
        return [_field_value_to_python(e) for e in fv.array_value.elems]
    if which == "inline_value":
        return {k: _field_value_to_python(v) for k, v in fv.inline_value.args.items()}
    return None


def parse_dsl_response_to_dict(resp: dslcompiler_pb2.ParseDslResponse) -> dict:
    """Pure function -- translates a ParseDslResponse into the same
    {nodes, events, edges, start_id} shape PlanPage.jsx's loadFromParsed
    already consumes, with bare type_names and plain-JSON params (the
    reverse of _mission_graph_from_request). Raises HTTPException on a
    parse error so the route handler doesn't need its own error-shape
    logic."""
    if not resp.ok:
        raise HTTPException(
            status_code=422,
            detail="; ".join(e.message for e in resp.errors) or "DSL parse error",
        )
    mission = resp.mission
    return {
        "nodes": [
            {
                "instance_id": n.instance_id,
                "type_name": _bare_name(n.type_name),
                "params": {k: _field_value_to_python(v) for k, v in n.params.items()},
            }
            for n in mission.nodes
        ],
        "events": [
            {
                "instance_id": e.instance_id,
                "type_name": _bare_name(e.type_name),
                "params": {k: _field_value_to_python(v) for k, v in e.params.items()},
            }
            for e in mission.events
        ],
        "edges": [
            {"source": e.source, "event_id": e.event_id, "target": e.target}
            for e in mission.edges
        ],
        "start_id": mission.start_id,
        "role": mission.role,
        "imports": [
            {"alias": imp.alias, "path": imp.path, "version": imp.version}
            for imp in mission.imports
        ],
    }


class ParseDslRequest(BaseModel):
    dsl: str


@router.post("/api/parse_dsl")
async def parse_dsl(request: ParseDslRequest):
    client = _current_dslcompiler_client()
    try:
        resp = await client.parse_dsl(request.dsl)
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return parse_dsl_response_to_dict(resp)


def _bare_name(qualified: str) -> str:
    """'actions.Patrol' -> 'Patrol'. Every qualified name this service
    produces is 'qualifier.Name' with no further dots in the qualifier
    (see the dslcompiler design doc's Schema section), so the part after
    the last '.' is always the bare display name."""
    return qualified.rsplit(".", 1)[-1]


def _type_name_index(qualified_names) -> dict[str, str]:
    """Builds a bare-name -> qualified-name lookup, e.g. {'Patrol':
    'actions.Patrol'}. If two qualified names share a bare name (not the
    case for the current default import set), the later one wins --
    matches today's flat, collision-free Python-SDK-era registry closely
    enough that this isn't worth guarding further here."""
    return {_bare_name(name): name for name in qualified_names}


def _field_schema_to_dict(field: dslcompiler_pb2.FieldSchema) -> dict:
    entry: dict = {
        "name": field.name,
        "type": field.type,
        "required": field.required,
        "description": field.description,
    }
    if field.HasField("default_value"):
        entry["default"] = field.default_value
    if field.HasField("object_type"):
        entry["object_type"] = _bare_name(field.object_type)
    if field.HasField("enum_type"):
        entry["enum_type"] = _bare_name(field.enum_type)
    if field.map_feature:
        entry["map_feature"] = True
    if field.nested_fields:
        entry["nested_fields"] = [_field_schema_to_dict(f) for f in field.nested_fields]
    return entry


def _type_schemas_to_dict(schemas: dict[str, dslcompiler_pb2.TypeSchema]) -> dict:
    return {
        _bare_name(name): {
            "description": ts.description,
            "fields": [_field_schema_to_dict(f) for f in ts.fields],
        }
        for name, ts in schemas.items()
    }


def _enum_schemas_to_dict(schemas: dict[str, dslcompiler_pb2.EnumSchema]) -> dict:
    return {
        _bare_name(name): {
            "description": es.description,
            "values": list(es.values),
        }
        for name, es in schemas.items()
    }


def build_schema_response(resp: dslcompiler_pb2.GetSchemaResponse) -> dict:
    """Pure function -- translates the dslcompiler service's qualified-name
    schema into the bare-name-keyed shape the frontend already consumes
    (see this plan's Global Constraints on why bare names are load-bearing
    here, not cosmetic)."""
    result = {
        "actions": _type_schemas_to_dict(resp.actions),
        "events": _type_schemas_to_dict(resp.events),
        "enums": _enum_schemas_to_dict(resp.enums),
        "imports": [
            {"alias": imp.alias, "path": imp.path, "version": imp.version}
            for imp in resp.imports
        ],
        "default_role": resp.default_role,
    }
    if not result["actions"] and not result["events"]:
        raise HTTPException(
            status_code=500,
            detail="Schema registry is empty — dslcompiler service returned nothing",
        )
    return result


@router.get("/api/schema")
async def get_schema():
    client = _current_dslcompiler_client()
    try:
        resp = await client.get_schema()
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return build_schema_response(resp)


class CompileNode(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class CompileEvent(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class CompileEdge(BaseModel):
    source: str
    event_id: str
    target: str


class CompileRequest(BaseModel):
    nodes: list[CompileNode]
    events: list[CompileEvent]
    edges: list[CompileEdge]
    start_id: str


def _field_value_from_python(
    value, field_schema: dslcompiler_pb2.FieldSchema | None
) -> dslcompiler_pb2.FieldValue:
    """Converts one plain-JSON param value (what the current frontend still
    sends -- Phase 2 is what will let it send FieldValue's oneof kind
    explicitly) into a typed FieldValue, using field_schema (when known)
    to resolve the one real ambiguity: whether a string names an enum
    constant (ident_ref) or is a literal string value. bool is checked
    before int since Python's bool is an int subclass."""
    if isinstance(value, bool):
        return dslcompiler_pb2.FieldValue(bool_value=value)
    if (
        field_schema is not None
        and field_schema.HasField("enum_type")
        and isinstance(value, str)
    ):
        return dslcompiler_pb2.FieldValue(ident_ref=value)
    if isinstance(value, int):
        return dslcompiler_pb2.FieldValue(int_value=value)
    if isinstance(value, float):
        return dslcompiler_pb2.FieldValue(float_value=value)
    if isinstance(value, str):
        return dslcompiler_pb2.FieldValue(string_value=value)
    if isinstance(value, list):
        return dslcompiler_pb2.FieldValue(
            array_value=dslcompiler_pb2.FieldValueArray(
                elems=[_field_value_from_python(v, None) for v in value]
            )
        )
    if isinstance(value, dict):
        nested_by_name = (
            {f.name: f for f in field_schema.nested_fields} if field_schema else {}
        )
        return dslcompiler_pb2.FieldValue(
            inline_value=dslcompiler_pb2.InlineCtorValue(
                type_name=field_schema.object_type if field_schema else "",
                args={
                    k: _field_value_from_python(v, nested_by_name.get(k))
                    for k, v in value.items()
                },
            )
        )
    raise ValueError(f"Unsupported param value: {value!r}")


def _params_to_field_values(
    params: dict, fields_by_name: dict[str, dslcompiler_pb2.FieldSchema]
) -> dict[str, dslcompiler_pb2.FieldValue]:
    return {
        k: _field_value_from_python(v, fields_by_name.get(k)) for k, v in params.items()
    }


def _mission_graph_from_request(
    request: "CompileRequest", schema: dslcompiler_pb2.GetSchemaResponse
) -> dslcompiler_pb2.MissionGraph:
    """Translates the frontend's bare-name, untyped-JSON graph shape into
    the qualified-name, typed-FieldValue MissionGraph Validate/Build
    expect. An unknown bare type_name is passed through unqualified
    rather than rejected here -- Validate's own registry lookup reports a
    clear "unknown type" error naming it, so there's no need to duplicate
    that check locally (see the design doc's Graph -> AST Construction
    section on what stays a local structural check vs. what Validate
    itself is responsible for)."""
    action_index = _type_name_index(schema.actions.keys())
    event_index = _type_name_index(schema.events.keys())

    nodes = [
        dslcompiler_pb2.Node(
            instance_id=n.instance_id,
            type_name=action_index.get(n.type_name, n.type_name),
            params=_params_to_field_values(
                n.params,
                {
                    f.name: f
                    for f in schema.actions.get(
                        action_index.get(n.type_name, n.type_name),
                        dslcompiler_pb2.TypeSchema(),
                    ).fields
                },
            ),
        )
        for n in request.nodes
    ]
    events = [
        dslcompiler_pb2.EventInstance(
            instance_id=e.instance_id,
            type_name=event_index.get(e.type_name, e.type_name),
            params=_params_to_field_values(
                e.params,
                {
                    f.name: f
                    for f in schema.events.get(
                        event_index.get(e.type_name, e.type_name),
                        dslcompiler_pb2.TypeSchema(),
                    ).fields
                },
            ),
        )
        for e in request.events
    ]
    edges = [
        dslcompiler_pb2.Edge(source=e.source, event_id=e.event_id, target=e.target)
        for e in request.edges
    ]
    return dslcompiler_pb2.MissionGraph(
        nodes=nodes, events=events, edges=edges, start_id=request.start_id
    )


async def compile_mission(
    request: CompileRequest,
    client: DslCompilerClient,
    schema: dslcompiler_pb2.GetSchemaResponse,
) -> dict:
    """Pure-ish function (one gRPC call) -- safe to test with a
    FakeDslCompilerClient, no live server needed. Structural checks
    (duplicate ids, dangling edges, start_id) run locally first, exactly
    as before; only "does this type/these params actually type-check
    against the SDK" now goes over gRPC to Validate."""
    errors: list[dict] = []

    seen_ids: set[str] = set()
    for node in request.nodes:
        if node.instance_id in seen_ids:
            errors.append(
                {
                    "node_id": node.instance_id,
                    "message": f"Duplicate node instance_id: '{node.instance_id}'",
                }
            )
        seen_ids.add(node.instance_id)
    seen_event_ids: set[str] = set()
    for ev in request.events:
        if ev.instance_id in seen_event_ids:
            errors.append(
                {
                    "node_id": ev.instance_id,
                    "message": f"Duplicate event instance_id: '{ev.instance_id}'",
                }
            )
        seen_event_ids.add(ev.instance_id)

    node_ids = {n.instance_id for n in request.nodes}
    if request.start_id not in node_ids:
        errors.append(
            {
                "node_id": request.start_id,
                "message": f"start_id '{request.start_id}' does not refer to any node",
            }
        )

    event_ids = {ev.instance_id for ev in request.events} | {"done"}
    for edge in request.edges:
        if edge.source not in node_ids:
            errors.append(
                {
                    "node_id": edge.source,
                    "message": f"Edge source '{edge.source}' does not refer to any node",
                }
            )
        if edge.target not in node_ids:
            errors.append(
                {
                    "node_id": edge.target,
                    "message": f"Edge target '{edge.target}' does not refer to any node",
                }
            )
        if edge.event_id not in event_ids:
            errors.append(
                {
                    "node_id": edge.event_id,
                    "message": f"Edge event_id '{edge.event_id}' does not refer to any declared event",
                }
            )

    if errors:
        return {"errors": errors}

    try:
        mission = _mission_graph_from_request(request, schema)
    except ValueError as e:
        return {"errors": [{"node_id": None, "message": str(e)}]}
    try:
        validate_resp = await client.validate(mission)
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    if not validate_resp.ok:
        return {
            "errors": [
                {
                    "node_id": e.node_id if e.HasField("node_id") else None,
                    "event_id": e.event_id if e.HasField("event_id") else None,
                    "message": e.message,
                }
                for e in validate_resp.errors
            ]
        }

    return {"ok": True}


@router.post("/api/compile")
async def compile_mission_route(request: CompileRequest) -> dict:
    client = _current_dslcompiler_client()
    try:
        schema = await client.get_schema()
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return await compile_mission(request, client, schema)


class BuildMissionRequest(CompileRequest):
    arch: Literal["amd64", "arm64"]
    geojson: str = ""  # the Map tab's drawn features, raw GeoJSON text; "" means no map


async def _build_stream_for_arch(
    client: DslCompilerClient, mission, arch: str, geojson: bytes = b""
):
    """Relays only the BuildChunks for arch out of the service's combined
    amd64+arm64 stream, yielding raw bytes. Raises HTTPException (rather
    than yielding an error indicator) if the FIRST chunk seen for arch
    carries errors, since that happens before any response bytes have
    been sent -- the caller must consume at least one item from this
    generator inside a try/except before handing it to StreamingResponse,
    exactly as the route below does, or the error will surface as a
    broken stream instead of a clean 422."""
    stream = client.build(mission, geojson=geojson)
    async for chunk in stream:
        if chunk.arch != arch:
            continue
        if chunk.errors:
            detail = "; ".join(e.message for e in chunk.errors)
            raise HTTPException(
                status_code=422, detail=f"Build failed for {arch}: {detail}"
            )
        yield chunk.data
        if chunk.done:
            return


@router.post("/api/build")
async def build_route(request: BuildMissionRequest):
    client = _current_dslcompiler_client()
    try:
        schema = await client.get_schema()
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    try:
        mission = _mission_graph_from_request(request, schema)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    stream = _build_stream_for_arch(
        client, mission, request.arch, geojson=request.geojson.encode("utf-8")
    )
    try:
        first_piece = await anext(stream)
    except StopAsyncIteration:
        raise HTTPException(
            status_code=500,
            detail=f"Build stream ended without producing arch '{request.arch}'",
        ) from None
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e

    async def _relay():
        yield first_piece
        async for piece in stream:
            yield piece

    return StreamingResponse(
        _relay(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="mission-{request.arch}"'
        },
    )
