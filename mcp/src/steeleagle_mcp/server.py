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
from pathlib import Path
from typing import Any

_SDK_SRC = Path(__file__).resolve().parents[3] / "sdk" / "src"
if _SDK_SRC.is_dir() and str(_SDK_SRC) not in sys.path:
    sys.path.insert(0, str(_SDK_SRC))

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

from steeleagle_mcp.config import load_config, make_server_parser, setup_logging
from steeleagle_mcp.mission_tools import (
    compile_mission_dsl_payload,
    save_mission_artifacts_payload,
    translate_with_dsl_reference_payload,
)

logger = logging.getLogger("server")

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
    logger.info("SDK init: kernel=%s telem=%s results=%s",
             drone_cfg["kernel"], drone_cfg["telemetry"], drone_cfg["results"])

    types.VEHICLE = Vehicle(_channel, _store)
    types.COMPUTE = Compute(_channel, _store)


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


def _serialize_payload(payload: dict[str, Any]) -> str:
    """Serialize explicit MCP tool payloads without ASCII escaping."""
    return json.dumps(payload, ensure_ascii=False, default=str)


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

    async def action_tool(_cls=cls, _name=name, **kwargs) -> str:
        logger.info("action %s called  args=%s", _name, kwargs)
        try:
            instance = _cls(**kwargs)
        except Exception:
            logger.exception("action %s instantiation failed  args=%s", _name, kwargs)
            raise
        try:
            result = await instance.execute()
        except Exception:
            logger.exception("action %s execution failed", _name)
            raise
        serialized = _serialize(result)
        logger.info("action %s result  %s", _name, serialized)
        return serialized

    action_tool.__name__ = name
    action_tool.__doc__ = doc
    action_tool.__signature__ = _make_signature(cls)
    mcp.tool(name=name, description=f"[Action] {doc}")(action_tool)




def _register_all() -> None:
    """Load DSL registry and register all tools."""
    load_all()
    logger.info("DSL registry: %d actions, %d events", len(_ACTIONS), len(_EVENTS))

    # Register actions as individual tools
    for name, cls in _ACTIONS.items():
        _register_action(name, cls)

    # Events are NOT registered as individual tools - they're only accessible via racer
    # This enforces the pattern that events are conditions, not standalone operations

    # Log what was registered
    action_tools = list(_ACTIONS.keys())
    logger.info("Registered %d action tools: %s", len(action_tools), ", ".join(sorted(action_tools)))
    logger.info("Events are available only through racer tool: %s", ", ".join(sorted(_EVENTS.keys())))


# Register tools at import time so `mcp dev server.py` works
_register_all()


# ---------------------------------------------------------------------------
# Racer tool: race an action against events
# ---------------------------------------------------------------------------


@mcp.tool(
    name="racer",
    description=(
        "Race an action against events - returns whichever completes first. "
        "Use ONLY when you need timeout, safety monitoring, or early termination. "
        "DO NOT use for normal action execution - call the action directly instead. "
        "REQUIRED: action (str), action_params (dict, use {} if empty), events (list, min 1 event). "
        "Example: racer(action='patrol', action_params={'waypoints': {...}}, "
        "events=[{'name': 'timereached', 'params': {'duration': 300}}])"
    ),
)
async def racer(
    action: str,
    action_params: dict[str, Any],
    events: list[dict[str, Any]],
) -> str:
    """Race an action against a list of events.

    Args:
        action: Name of the DSL action to execute (required)
        action_params: Dictionary of parameters for the action (required, use {} if none)
        events: List of event specs with 'name' and 'params' keys (required, must have at least 1)

    Returns:
        JSON result of whichever completes first (action or event)

    Example:
        {
            "action": "patrol",
            "action_params": {"waypoints": [...]},
            "events": [
                {"name": "timereached", "params": {"duration": 300}},
                {"name": "batteryreached", "params": {"threshold": 20}}
            ]
        }
    """
    logger.info("racer called  action=%s events=%d", action, len(events))

    # Validate events list is not empty
    if not events:
        error_msg = "events list cannot be empty - provide at least one event to race against"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

    # Validate action exists
    if action not in _ACTIONS:
        error_msg = f"Unknown action: {action}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

    # Validate events
    for i, event_spec in enumerate(events):
        if "name" not in event_spec or "params" not in event_spec:
            error_msg = f"Event {i} missing 'name' or 'params'"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

        # Normalize event name: strip "check_" prefix if present (for backward compatibility)
        # Events are now only accessible via racer, so "check_" prefix is optional
        event_name = event_spec["name"]
        if event_name.startswith("check_"):
            event_name = event_name[6:]  # Remove "check_" prefix

        if event_name not in _EVENTS:
            error_msg = f"Unknown event: {event_spec['name']} (normalized: {event_name})"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

        # Update the event_spec with normalized name
        event_spec["name"] = event_name

    async def run_action():
        """Execute the action and return result with metadata."""
        try:
            action_cls = _ACTIONS[action]
            instance = action_cls(**action_params)
            result = await instance.execute()
            return {
                "type": "action",
                "name": action,
                "result": result,
            }
        except Exception as e:
            logger.exception("racer: action %s failed", action)
            return {
                "type": "action",
                "name": action,
                "error": str(e),
            }

    async def run_event(event_name: str, event_params: dict):
        """Check an event and return result with metadata."""
        try:
            event_cls = _EVENTS[event_name]
            instance = event_cls(**event_params)
            result = await instance.check()
            return {
                "type": "event",
                "name": event_name,
                "result": result,
            }
        except Exception as e:
            logger.exception("racer: event %s failed", event_name)
            return {
                "type": "event",
                "name": event_name,
                "error": str(e),
            }

    # Create tasks for action and all events
    tasks = [asyncio.create_task(run_action())]
    for event_spec in events:
        tasks.append(
            asyncio.create_task(
                run_event(event_spec["name"], event_spec["params"])
            )
        )

    # Race them - return first to complete
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # Cancel pending tasks
    for task in pending:
        task.cancel()

    # Get the winner
    winner = done.pop()
    result_data = await winner

    # Format response based on what won
    if result_data["type"] == "action":
        if "error" in result_data:
            response = {
                "winner": "action",
                "action": result_data["name"],
                "error": result_data["error"],
                "events_triggered": [],
            }
        else:
            response = {
                "winner": "action",
                "action": result_data["name"],
                "action_result": result_data["result"],
                "events_triggered": [],
            }
    else:  # event
        if "error" in result_data:
            response = {
                "winner": "event",
                "event": result_data["name"],
                "error": result_data["error"],
                "action_completed": False,
            }
        else:
            response = {
                "winner": "event",
                "event": result_data["name"],
                "event_result": result_data["result"],
                "action_completed": False,
            }

    serialized = _serialize(response)
    logger.info("racer completed  winner=%s", result_data["type"])
    return serialized


# Log control flow tool registration
logger.info("Registered 1 control flow tool: racer")


# ---------------------------------------------------------------------------
# Mission artifact tools: reference-assisted DSL -> mission.json -> files
# ---------------------------------------------------------------------------


@mcp.tool(
    name="translate_with_dsl_reference",
    description=(
        "Prepare the reference needed for the caller LLM to translate a summarized natural-language "
        "mission into SteelEagle DSL without any server-side LLM or OpenAI API. Returns DSL grammar, "
        "action/event/data schema, generation rules, few-shot examples, and common mistakes. "
        "Optionally validates a candidate_dsl through the deterministic validator/compiler. "
        "Does not execute, upload, or start the mission."
    ),
)
async def translate_with_dsl_reference(
    instruction: str,
    language: str = "auto",
    focus: str = "all",
    include_schema: bool = True,
    include_examples: bool = True,
    include_grammar: bool = True,
    include_common_mistakes: bool = True,
    candidate_dsl: str | None = None,
    max_examples: int = 4,
) -> str:
    payload = translate_with_dsl_reference_payload(
        instruction=instruction,
        language=language,
        focus=focus,
        include_schema=include_schema,
        include_examples=include_examples,
        include_grammar=include_grammar,
        include_common_mistakes=include_common_mistakes,
        candidate_dsl=candidate_dsl,
        max_examples=max_examples,
    )
    return _serialize_payload(payload)


@mcp.tool(
    name="compile_mission_dsl",
    description=(
        "Normalize, validate, and compile SteelEagle DSL into mission JSON. "
        "Use for DSL written by the caller LLM after translate_with_dsl_reference, "
        "or DSL the user edited manually. "
        "Returns normalized DSL, mission_json for chat preview, compile_id for saving, "
        "auto-fixes, and actionable validation/compiler errors."
    ),
)
async def compile_mission_dsl(
    dsl: str,
    return_ir: bool = True,
    include_normalized_dsl: bool = True,
) -> str:
    payload = compile_mission_dsl_payload(
        dsl=dsl,
        return_ir=return_ir,
        include_normalized_dsl=include_normalized_dsl,
    )
    return _serialize_payload(payload)


@mcp.tool(
    name="save_mission_artifacts",
    description=(
        "Save mission DSL and mission JSON to local artifact files. "
        "Pass normalized DSL plus compile_id returned by compile_mission_dsl. "
        "Do not pass mission_json or mission_json_text in normal use; the tool saves "
        "the exact mission JSON cached from the compile step. "
        "Defaults to steeleagle/mcp/artifacts/missions and refuses to overwrite "
        "unless overwrite=true. This does not execute, upload, or start the mission."
    ),
)
async def save_mission_artifacts(
    dsl: str,
    compile_id: str,
    basename: str = "mission",
    output_dir: str = "",
    overwrite: bool = False,
    add_timestamp: bool = True,
) -> str:
    payload = save_mission_artifacts_payload(
        dsl=dsl,
        compile_id=compile_id,
        basename=basename,
        output_dir=output_dir,
        overwrite=overwrite,
        add_timestamp=add_timestamp,
    )
    return _serialize_payload(payload)


logger.info(
    "Registered 3 mission artifact tools: translate_with_dsl_reference, "
    "compile_mission_dsl, save_mission_artifacts"
)


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
    """Create a Starlette ASGI app that uses the SSE transport."""
    transport = get_sse_transport()
    return Starlette(
        routes=[Mount(DEFAULT_SSE_ENDPOINT, app=transport.handle_post_message)]
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def amain(
    config: dict, transport: str = "stdio", host: str = "0.0.0.0", port: int = 8080
) -> None:
    """Async entry point: init SDK, run MCP server."""
    await _init_sdk(config["drone"], config["compute"])

    # Log available tools summary
    total_tools = len(_ACTIONS) + 4  # racer + 3 mission artifact tools
    logger.info("=" * 60)
    logger.info("MCP Server ready with %d tools available:", total_tools)
    logger.info("  - %d Action tools (execute drone commands)", len(_ACTIONS))
    logger.info("  - 1 Control flow tool (racer - provides access to %d events)", len(_EVENTS))
    logger.info("  - 3 Mission artifact tools (translate, compile, save)")
    logger.info("=" * 60)

    try:
        if transport == "stdio":
            await mcp.run_stdio_async()
        elif transport == "sse":
            logger.info("Starting SSE on http://%s:%d", host, port)
            await uvicorn.run(make_asgi_app(), host=host, port=port, log_level="info")
        elif transport == "streamable_http":
            logger.info("Starting streamable HTTP on http://%s:%d", host, port)
            await uvicorn.run(
                mcp.streamable_http_app, host=host, port=port, log_level="info"
            )
        else:
            raise ValueError(f"Unsupported transport mode: {transport}")
    finally:
        await _shutdown_sdk()


def cli() -> None:
    """CLI entry point for steeleagle-mcp-server."""
    setup_logging()
    parser = make_server_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    asyncio.run(amain(config, transport=args.transport, host=args.host, port=args.port))
