# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""MCP Server for SteelEagle drone control.

Dynamically registers:
- DSL Actions as individual @mcp.tool() (execute)
- DSL Events as individual @mcp.tool() (check)
"""

import asyncio
import inspect
import json
import logging
import sys
from typing import Any

import grpc
import uvicorn
from google.protobuf.json_format import MessageToDict
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount
from steeleagle_sdk.api.compute import Compute
from steeleagle_sdk.api.mission_store import MissionStore
from steeleagle_sdk.api.vehicle import Vehicle
from steeleagle_sdk.dsl import types
from steeleagle_sdk.dsl.compiler.loader import load_all
from steeleagle_sdk.dsl.compiler.registry import _ACTIONS, _EVENTS

from steeleagle_mcp.config import load_config, make_server_parser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level SDK state
# ---------------------------------------------------------------------------
_store: MissionStore | None = None
_channel: grpc.aio.Channel | None = None


async def _init_sdk(drone_cfg: dict, compute_cfg: dict) -> None:
    """Initialize SDK and set DSL globals (types.VEHICLE, types.COMPUTE)."""
    global _store, _channel

    _channel = grpc.aio.insecure_channel(drone_cfg["kernel"])
    _store = MissionStore(
        drone_cfg["telemetry"],
        drone_cfg["results"],
        compute_cfg.get("db_path", "mcp_mission.db"),
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


DEFAULT_SSE_ENDPOINT = "/messages/"


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
# FastMCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("steeleagle-mcp")


# ---------------------------------------------------------------------------
# Tool registration: DSL Actions + Events as individual @mcp.tool()
# ---------------------------------------------------------------------------


def _make_signature(cls: type) -> inspect.Signature:
    """Build an inspect.Signature from a Pydantic model's fields.

    FastMCP reads __signature__ to generate the tool's input schema,
    so this gives each tool flat, typed parameters (no 'params' wrapper).
    Required fields come first to satisfy Python signature ordering.
    """
    required, optional = [], []
    for field_name, field_info in cls.model_fields.items():
        if field_info.is_required():
            required.append(
                inspect.Parameter(
                    field_name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=field_info.annotation,
                )
            )
        else:
            optional.append(
                inspect.Parameter(
                    field_name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=field_info.default,
                    annotation=field_info.annotation,
                )
            )
    return inspect.Signature(required + optional)


def _register_action(name: str, cls: type) -> None:
    """Register a single DSL Action class as an @mcp.tool()."""
    doc = (cls.__doc__ or f"Execute {cls.__name__}.").strip()

    async def action_tool(_cls=cls, **kwargs) -> str:
        instance = _cls(**kwargs)
        result = await instance.execute()
        return _serialize(result)

    action_tool.__name__ = name
    action_tool.__doc__ = doc
    action_tool.__signature__ = _make_signature(cls)
    mcp.tool(name=name, description=f"[Action] {doc}")(action_tool)
    logger.info("  action tool: %s", name)


def _register_event(name: str, cls: type) -> None:
    """Register a single DSL Event class as an @mcp.tool()."""
    doc = (cls.__doc__ or f"Check if {cls.__name__} is satisfied.").strip()
    tool_name = f"check_{name}"

    async def event_tool(_cls=cls, **kwargs) -> str:
        instance = _cls(**kwargs)
        result = await instance.check()
        return _serialize(result)

    event_tool.__name__ = tool_name
    event_tool.__doc__ = doc
    event_tool.__signature__ = _make_signature(cls)
    mcp.tool(name=tool_name, description=f"[Event] {doc}")(event_tool)
    logger.info("  event tool: %s", tool_name)


def _register_all() -> None:
    """Load DSL registry and register all tools."""
    load_all()
    logger.info(
        "DSL registry: %d actions, %d events",
        len(_ACTIONS),
        len(_EVENTS),
    )

    for name, cls in _ACTIONS.items():
        _register_action(name, cls)

    for name, cls in _EVENTS.items():
        _register_event(name, cls)


# Register tools at import time so `mcp dev server.py` works
_register_all()


# ---------------------------------------------------------------------------
# ASGI Application
# ---------------------------------------------------------------------------


_sse_transport: SseServerTransport | None = None


def get_sse_transport() -> SseServerTransport:
    """Get or create the SSE server transport for ASGI."""
    global _sse_transport
    if _sse_transport is None:
        _sse_transport = SseServerTransport(DEFAULT_SSE_ENDPOINT)
    return _sse_transport


def make_asgi_app() -> Starlette:
    """Create a Starlette ASGI app that uses the SSE transport.

    This creates an ASGI application that can be used with ASGI servers like
    uvicorn or gunicorn. It handles the MCP protocol over HTTP using SSE.
    """
    transport = get_sse_transport()
    app = Starlette(
        routes=[Mount(DEFAULT_SSE_ENDPOINT, app=transport.handle_post_message)]
    )
    return app


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def amain(
    config: dict, transport: str = "stdio", host: str = "0.0.0.0", port: int = 8080
) -> None:
    """Async entry point: init SDK, run MCP server.

    Args:
        config: Server configuration dictionary
        transport: Transport mode ("stdio", "sse", or "streamable_http")
        host: Host for HTTP transport (unused for stdio)
        port: Port for HTTP transport (unused for stdio)
    """
    await _init_sdk(config["drone"], config["compute"])
    try:
        if transport == "stdio":
            await mcp.run_stdio_async()
        elif transport == "sse":
            logger.info(f"Starting SSE server on http://{host}:{port}")
            await uvicorn.run(make_asgi_app(), host=host, port=port, log_level="info")
        elif transport == "streamable_http":
            logger.info(f"Starting streamable HTTP server on http://{host}:{port}")
            await uvicorn.run(
                mcp.streamable_http_app, host=host, port=port, log_level="info"
            )
        else:
            raise ValueError(f"Unsupported transport mode: {transport}")
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

    asyncio.run(amain(config, transport=args.transport, host=args.host, port=args.port))
