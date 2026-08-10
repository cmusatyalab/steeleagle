"""Mission-only chat agent: LLM + in-process NL2DSL tools (no MCP server)."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any


def _ensure_mcp_on_path() -> None:
    """Make steeleagle_mcp importable even if the editable .pth install is broken."""
    try:
        import steeleagle_mcp  # noqa: F401

        return
    except ImportError:
        pass
    mcp_src = Path(__file__).resolve().parents[4] / "mcp" / "src"
    if mcp_src.is_dir() and str(mcp_src) not in sys.path:
        sys.path.insert(0, str(mcp_src))


_ensure_mcp_on_path()

from steeleagle_mcp.config import load_config  # noqa: E402
from steeleagle_mcp.mission_tools import (  # noqa: E402
    compile_mission_dsl_payload,
    translate_with_dsl_reference_payload,
)
from steeleagle_mcp.providers.anthropic import AnthropicProvider  # noqa: E402
from steeleagle_mcp.providers.openai import OpenAIProvider  # noqa: E402

from app.dsl_graph import get_dsl_parser, parse_dsl_to_graph  # noqa: E402

logger = logging.getLogger("chat_agent")

MAX_TOOL_ROUNDS = 8

_API_KEY_FIELDS = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}
_ENV_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

StatusCallback = Callable[[str, str], Awaitable[None]]

MISSION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "translate_with_dsl_reference",
        "description": (
            "Prepare the reference needed for the caller LLM to translate a summarized "
            "natural-language mission into SteelEagle DSL without any server-side LLM. "
            "Returns DSL grammar, action/event/data schema, generation rules, few-shot "
            "examples, and common mistakes. Optionally validates a candidate_dsl. "
            "Does not execute, upload, or start the mission."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "Concise mission summary for DSL generation",
                },
                "language": {
                    "type": "string",
                    "enum": ["auto", "zh", "en"],
                    "default": "auto",
                },
                "focus": {
                    "type": "string",
                    "default": "all",
                },
                "include_schema": {"type": "boolean", "default": True},
                "include_examples": {"type": "boolean", "default": True},
                "include_grammar": {"type": "boolean", "default": True},
                "include_common_mistakes": {"type": "boolean", "default": True},
                "candidate_dsl": {
                    "type": "string",
                    "description": "Optional draft DSL to validate against the pipeline",
                },
                "max_examples": {"type": "integer", "default": 4},
            },
            "required": ["instruction"],
        },
    },
    {
        "name": "compile_mission_dsl",
        "description": (
            "Normalize, validate, and compile SteelEagle DSL into mission JSON. "
            "Use after writing DSL from translate_with_dsl_reference, or when revising "
            "an existing draft. Returns normalized_dsl, mission_json, auto_fixes, and errors. "
            "Does not save files, upload, or start the mission."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dsl": {
                    "type": "string",
                    "description": "Complete SteelEagle mission DSL to compile",
                },
                "return_ir": {"type": "boolean", "default": True},
                "include_normalized_dsl": {"type": "boolean", "default": True},
            },
            "required": ["dsl"],
        },
    },
]

SYSTEM_PROMPT = """You are the GCS Assistant for SteelEagle mission planning inside the Plan page Chat tab.

You help operators:
1. Answer questions about available FSM actions / mission structure.
2. Turn natural-language mission requests into SteelEagle DSL.
3. Revise the current draft mission when the user asks for changes.

## Tools (whitelist — only these exist)

- **translate_with_dsl_reference**: Fetch grammar, schema, examples, and rules for writing DSL.
  Pass a concise `instruction` summary (not the whole raw chat). If revising, you may pass
  `candidate_dsl` with the current draft.
- **compile_mission_dsl**: Validate/compile DSL. On errors, fix and call again.

Do NOT call any other tools. There is no save/upload/start/takeoff tool. Never claim you
uploaded or started a mission.

## Mission workflow

1. Summarize the user's intent (and any current draft) into one clear instruction.
2. Call translate_with_dsl_reference(instruction=...).
3. Write a complete mission.dsl using the reference.
4. Call compile_mission_dsl(dsl=...).
5. If compile fails, revise using the errors and compile again.
6. When compile succeeds, reply with a short explanation and the full normalized DSL in a
   fenced ```dsl code block. Offer that the user can Apply it to the FSM Builder.

## Current draft

If the request includes a current draft DSL, treat it as the last known-good mission and
edit from that instead of starting from scratch unless the user asks for a brand-new plan.

## Safety

- Never instruct or pretend to execute vehicle control (takeoff, land, upload, start).
- Chat only produces reviewable mission drafts for the FSM Builder.
"""


def default_mcp_config_path() -> Path:
    env = os.environ.get("STEELEAGLE_MCP_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    # gcs/react/backend/app -> repo root / mcp/config.toml
    return Path(__file__).resolve().parents[4] / "mcp" / "config.toml"


def resolve_api_key(client_cfg: dict, provider: str) -> str | None:
    key_field = _API_KEY_FIELDS.get(provider)
    env_var = _ENV_VARS.get(provider)
    if not key_field or not env_var:
        return None
    key = client_cfg.get(key_field) or os.environ.get(env_var)
    return key.strip() if isinstance(key, str) and key.strip() else None


def load_client_settings(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or default_mcp_config_path()
    cfg = load_config(str(path) if path.is_file() else None)
    client = cfg.get("client") or {}
    provider = (client.get("provider") or "openai").strip().lower()
    model = client.get("model") or (
        "gpt-4o" if provider == "openai" else "claude-sonnet-4-20250514"
    )
    base_url = (client.get("openai_base_url") or "").strip()
    api_key = resolve_api_key(client, provider)
    return {
        "config_path": str(path),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
    }


def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "translate_with_dsl_reference":
        return translate_with_dsl_reference_payload(**args)
    if name == "compile_mission_dsl":
        return compile_mission_dsl_payload(**args)
    return {
        "ok": False,
        "errors": [f"Unknown or disallowed tool: {name}"],
    }


def _artifact_from_compiled(
    normalized_dsl: str,
    summary: str,
) -> dict[str, Any] | None:
    if get_dsl_parser() is None:
        logger.warning("DSL parser unavailable; skipping Apply artifact")
        return None
    try:
        graph = parse_dsl_to_graph(normalized_dsl)
    except Exception:
        logger.exception("Failed to parse normalized DSL into FSM graph")
        return None
    nodes = graph.get("nodes") or []
    if not nodes:
        return None
    return {
        "id": f"artifact-{uuid.uuid4().hex[:10]}",
        "type": "mission-draft",
        "target": "fsm-builder",
        "label": "Apply draft to FSM Builder",
        "payload": {
            "summary": summary,
            "nodes": nodes,
            "events": graph.get("events") or [],
            "edges": graph.get("edges") or [],
            "start_id": graph.get("start_id") or nodes[0].get("instance_id"),
            "normalized_dsl": normalized_dsl,
        },
    }


def _extract_last_compile(tool_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    for payload in reversed(tool_results):
        if not isinstance(payload, dict):
            continue
        if "normalized_dsl" in payload and "compile_id" in payload:
            return payload
    return None


def _last_user_text(messages: list[dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user" and m.get("content"):
            return str(m["content"])
    return ""


async def _noop_status(phase: str, detail: str) -> None:
    return None


async def run_chat_turn(
    messages: list[dict[str, str]],
    draft_dsl: str | None = None,
    *,
    on_status: StatusCallback | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """
    Run one mission-only agent turn.

    Returns:
      { content, artifacts, draft } on success
      raises ValueError for configuration problems
    """
    status = on_status or _noop_status
    settings = load_client_settings(config_path)
    provider_name = settings["provider"]
    api_key = settings["api_key"]
    if not api_key:
        env_hint = _ENV_VARS.get(provider_name, "OPENAI_API_KEY / ANTHROPIC_API_KEY")
        raise ValueError(
            f"No API key for provider '{provider_name}'. "
            f"Set {env_hint} or add it under [client] in {settings['config_path']}."
        )
    if provider_name not in {"openai", "anthropic"}:
        raise ValueError(f"Unsupported provider '{provider_name}'. Use openai or anthropic.")

    working_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in {"user", "assistant"} and m.get("content")
    ]
    if draft_dsl and draft_dsl.strip():
        working_messages.insert(
            0,
            {
                "role": "user",
                "content": (
                    "Current draft mission DSL (last known-good). "
                    "Revise from this when the user asks for changes:\n"
                    f"```dsl\n{draft_dsl.strip()}\n```"
                ),
            },
        )

    system = SYSTEM_PROMPT
    tool_payloads: list[dict[str, Any]] = []

    if provider_name == "openai":
        content = await _run_openai(
            settings, working_messages, system, tool_payloads, status
        )
    else:
        content = await _run_anthropic(
            settings, working_messages, system, tool_payloads, status
        )

    compiled = _extract_last_compile(tool_payloads)
    artifacts: list[dict[str, Any]] = []
    draft: dict[str, str] | None = None
    if compiled and compiled.get("ok") and compiled.get("normalized_dsl"):
        normalized = compiled["normalized_dsl"]
        draft = {"normalized_dsl": normalized}
        art = _artifact_from_compiled(normalized, _last_user_text(messages))
        if art:
            artifacts.append(art)
    elif draft_dsl and draft_dsl.strip():
        draft = {"normalized_dsl": draft_dsl.strip()}

    if not (content or "").strip():
        content = (
            "I finished processing your request, but had nothing to say. "
            "Try asking me to draft or revise a mission."
        )

    return {"content": content, "artifacts": artifacts, "draft": draft}


async def _run_openai(
    settings: dict[str, Any],
    messages: list[dict[str, Any]],
    system: str,
    tool_payloads: list[dict[str, Any]],
    status: StatusCallback,
) -> str:
    provider = OpenAIProvider(settings.get("base_url") or "")
    client = provider.create_client(settings["api_key"])
    tools = provider.tools_to_provider_format(MISSION_TOOLS)
    history: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
    final_text = ""

    for _round in range(MAX_TOOL_ROUNDS):
        await status("llm", f"Calling {settings['model']}")
        response = client.chat.completions.create(
            model=settings["model"],
            messages=history,
            tools=tools,
            max_completion_tokens=4096,
        )
        choice = response.choices[0]
        message = choice.message
        assistant_msg = message.model_dump(exclude_none=True)
        assistant_msg["role"] = "assistant"
        history.append(assistant_msg)

        if message.content:
            final_text = message.content

        tool_calls = message.tool_calls or []
        if not tool_calls:
            break

        for tc in tool_calls:
            name = tc.function.name
            raw = tc.function.arguments
            try:
                args = json.loads(raw) if isinstance(raw, str) and raw else {}
            except json.JSONDecodeError:
                args = {}
            await status("tool", f"Running {name}")
            payload = dispatch_tool(name, args if isinstance(args, dict) else {})
            tool_payloads.append(payload)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )
    else:
        final_text = (
            final_text
            or "I hit the tool-call limit while generating the mission. "
            "Please try again with a simpler request."
        )

    return final_text or ""


async def _run_anthropic(
    settings: dict[str, Any],
    messages: list[dict[str, Any]],
    system: str,
    tool_payloads: list[dict[str, Any]],
    status: StatusCallback,
) -> str:
    provider = AnthropicProvider()
    client = provider.create_client(settings["api_key"])
    tools = provider.tools_to_provider_format(MISSION_TOOLS)
    history: list[dict[str, Any]] = list(messages)
    final_text = ""

    for _round in range(MAX_TOOL_ROUNDS):
        await status("llm", f"Calling {settings['model']}")
        response = client.messages.create(
            model=settings["model"],
            messages=history,
            system=system,
            tools=tools,
            max_tokens=4096,
        )
        history.append({"role": "assistant", "content": response.content})

        text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
        if text_blocks:
            final_text = text_blocks[0].text

        tool_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if not tool_blocks:
            break

        result_content: list[dict[str, Any]] = []
        for block in tool_blocks:
            name = block.name
            args = block.input if isinstance(block.input, dict) else {}
            await status("tool", f"Running {name}")
            payload = dispatch_tool(name, args)
            tool_payloads.append(payload)
            result_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )
        history.append({"role": "user", "content": result_content})
    else:
        final_text = (
            final_text
            or "I hit the tool-call limit while generating the mission. "
            "Please try again with a simpler request."
        )

    return final_text or ""


async def iter_chat_events(
    messages: list[dict[str, str]],
    draft_dsl: str | None = None,
    *,
    config_path: Path | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Yield (event_name, data) for SSE: status / done / error."""
    import asyncio

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def emit_status(phase: str, detail: str) -> None:
        await queue.put(("status", {"phase": phase, "detail": detail}))

    async def worker() -> None:
        try:
            result = await run_chat_turn(
                messages,
                draft_dsl,
                on_status=emit_status,
                config_path=config_path,
            )
            await queue.put(("done", result))
        except ValueError as exc:
            await queue.put(("error", {"message": str(exc)}))
        except Exception as exc:
            logger.exception("chat turn failed")
            await queue.put(("error", {"message": str(exc)}))
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await task