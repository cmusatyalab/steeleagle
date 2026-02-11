"""MCP Server for SteelEagle drone control.

Dynamically registers:
- DSL Actions as individual @mcp.tool() (execute)
- DSL Events as individual @mcp.tool() (check)
- DSL Datatypes + Enums as MCP resources (reference for the LLM)
"""

import asyncio
import json
import logging
import sys
from enum import IntEnum
from typing import Any

import grpc
from google.protobuf.json_format import MessageToDict
from mcp.server.fastmcp import FastMCP
from mcp.types import Annotations

from steeleagle_sdk.api.compute import Compute
from steeleagle_sdk.api.mission_store import MissionStore
from steeleagle_sdk.api.vehicle import Vehicle
from steeleagle_sdk.dsl import types
from steeleagle_sdk.dsl.compiler.loader import load_all
from steeleagle_sdk.dsl.compiler.registry import _ACTIONS, _DATA, _EVENTS

from .config import load_config, make_server_parser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level SDK state
# ---------------------------------------------------------------------------
_store: MissionStore | None = None
_channel: grpc.aio.Channel | None = None


async def _init_sdk(drone_cfg: dict, mcp_cfg: dict) -> None:
    """Initialize SDK and set DSL globals (types.VEHICLE, types.COMPUTE)."""
    global _store, _channel

    _channel = grpc.aio.insecure_channel(drone_cfg["kernel"])
    _store = MissionStore(
        drone_cfg["telemetry"],
        drone_cfg["results"],
        mcp_cfg.get("db_path", "mcp_mission.db"),
    )
    await _store.start()
    logger.info(
        "MissionStore started (telemetry=%s, results=%s)",
        drone_cfg["telemetry"],
        drone_cfg["results"],
    )

    types.VEHICLE = Vehicle(_channel, _store)
    types.COMPUTE = Compute(_channel, _store)
    logger.info("SDK initialized: kernel=%s", drone_cfg["kernel"])


async def _shutdown_sdk() -> None:
    global _store, _channel
    if _store:
        try:
            await _store.stop()
        except Exception:
            logger.exception("Error stopping MissionStore")
    types.VEHICLE = None
    types.COMPUTE = None
    types.MAP = None
    _store = _channel = None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> str:
    """Serialize SDK response (Pydantic, protobuf, bool, or None) to JSON."""
    if obj is None:
        return json.dumps({"status": "no_data", "message": "No data available"})
    if isinstance(obj, bool):
        return json.dumps({"result": obj})
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), default=str)
    if hasattr(obj, "DESCRIPTOR"):
        return json.dumps(MessageToDict(obj, preserving_proto_field_name=True))
    return json.dumps({"result": str(obj)})


# ---------------------------------------------------------------------------
# Schema helpers (for resources only)
# ---------------------------------------------------------------------------


def _resolve_refs(schema: Any, defs: dict) -> Any:
    """Recursively inline $ref pointers so the schema is self-contained."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_name = schema["$ref"].rsplit("/", 1)[-1]
            if ref_name in defs:
                return _resolve_refs(defs[ref_name], defs)
            return schema
        return {k: _resolve_refs(v, defs) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_resolve_refs(item, defs) for item in schema]
    return schema


def _safe_schema(cls) -> dict:
    """Build a self-contained JSON Schema from a Pydantic class."""
    raw = cls.model_json_schema()
    defs = raw.pop("$defs", {})
    resolved = _resolve_refs(raw, defs)
    resolved.setdefault("type", "object")
    resolved.setdefault("properties", {})
    return resolved


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("steeleagle-mcp")


# ---------------------------------------------------------------------------
# Resource registry: DSL Datatypes + Enums
# ---------------------------------------------------------------------------
_RESOURCE_REGISTRY: dict[str, str] = {}  # uri -> JSON content


def _discover_enums() -> list[tuple[str, type]]:
    """Find int-based Enum classes in DSL datatype modules."""
    from enum import Enum as _Enum

    import steeleagle_sdk.dsl.types.datatypes.compute as compute_mod
    import steeleagle_sdk.dsl.types.datatypes.control as control_mod
    import steeleagle_sdk.dsl.types.datatypes.telemetry as telemetry_mod

    enums = []
    for mod in (control_mod, compute_mod, telemetry_mod):
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, (int, _Enum))
                and obj not in (int, _Enum, IntEnum)
                and hasattr(obj, "__members__")
            ):
                enums.append((attr_name, obj))
    return enums


def _register_resources() -> None:
    """Register MCP resources for datatypes and enums."""

    # Enums
    enums = _discover_enums()
    for cls_name, cls in enums:
        name = cls_name.lower()
        uri = f"steeleagle://enum/{name}"
        members = [{"name": m.name, "value": m.value} for m in cls]
        doc = (cls.__doc__ or "").strip()
        content = json.dumps(
            {"name": cls_name, "type": "enum", "description": doc, "members": members},
            indent=2,
        )
        _RESOURCE_REGISTRY[uri] = content
        mcp.resource(
            uri,
            name=cls_name,
            description=f"[Enum] {doc.split(chr(10))[0]}",
            mime_type="application/json",
            annotations=Annotations(audience=["assistant"], priority=0.5),
        )(_make_resource_reader(content))

    # Datatypes
    for name, cls in _DATA.items():
        uri = f"steeleagle://datatype/{name}"
        schema = _safe_schema(cls)
        doc = (cls.__doc__ or "").strip()
        content = json.dumps(
            {"name": name, "type": "datatype", "description": doc, "schema": schema},
            indent=2,
        )
        _RESOURCE_REGISTRY[uri] = content
        mcp.resource(
            uri,
            name=name,
            description=f"[Datatype] {doc.split(chr(10))[0]}",
            mime_type="application/json",
            annotations=Annotations(audience=["assistant"], priority=0.5),
        )(_make_resource_reader(content))

    logger.info("Resources: %d enums, %d datatypes", len(enums), len(_DATA))


def _make_resource_reader(content: str):
    """Create a resource reader closure for a static content string."""
    async def reader() -> str:
        return content
    return reader


# ---------------------------------------------------------------------------
# Tool registration: DSL Actions + Events as individual @mcp.tool()
# ---------------------------------------------------------------------------


def _register_action(name: str, cls: type) -> None:
    """Register a single DSL Action class as an @mcp.tool()."""
    doc = (cls.__doc__ or f"Execute {cls.__name__}.").strip()

    async def action_tool(params: cls) -> str:  # type: ignore[valid-type]
        result = await params.execute()
        return _serialize(result)

    action_tool.__name__ = name
    action_tool.__doc__ = doc
    mcp.tool(name=name, description=f"[Action] {doc}")(action_tool)
    logger.info("  action tool: %s", name)


def _register_event(name: str, cls: type) -> None:
    """Register a single DSL Event class as an @mcp.tool()."""
    doc = (cls.__doc__ or f"Check if {cls.__name__} is satisfied.").strip()
    tool_name = f"check_{name}"

    async def event_tool(params: cls) -> str:  # type: ignore[valid-type]
        result = await params.check()
        return _serialize(result)

    event_tool.__name__ = tool_name
    event_tool.__doc__ = doc
    mcp.tool(name=tool_name, description=f"[Event] {doc}")(event_tool)
    logger.info("  event tool: %s", tool_name)


def _register_all() -> None:
    """Load DSL registry and register all tools + resources."""
    load_all()
    logger.info(
        "DSL registry: %d actions, %d events, %d datatypes",
        len(_ACTIONS), len(_EVENTS), len(_DATA),
    )

    _register_resources()

    for name, cls in _ACTIONS.items():
        _register_action(name, cls)

    for name, cls in _EVENTS.items():
        _register_event(name, cls)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def amain(config: dict) -> None:
    """Async entry point: init SDK, run MCP server over stdio."""
    await _init_sdk(config["drone"], config["mcp"])
    try:
        await mcp.run_stdio_async()
    finally:
        await _shutdown_sdk()


def cli() -> None:
    """CLI entry point for steeleagle-mcp-server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    parser = make_server_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    _register_all()

    asyncio.run(amain(config))
