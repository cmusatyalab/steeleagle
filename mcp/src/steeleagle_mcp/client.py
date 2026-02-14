# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""MCP Client: Interactive chat REPL for drone mission planning via LLM providers.

Spawns the MCP server as a subprocess (stdio transport), discovers tools,
and runs an agentic loop: user message -> LLM API (with tools) -> execute
tool calls via MCP -> feed results back -> repeat until done.
"""

import asyncio
import logging
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from steeleagle_mcp.config import load_config, make_client_parser, setup_logging
from steeleagle_mcp.providers.anthropic import AnthropicProvider
from steeleagle_mcp.providers.openai import OpenAIProvider
from steeleagle_mcp.system_prompt import generate_system_prompt
from steeleagle_sdk.dsl.compiler.loader import load_all
from steeleagle_sdk.dsl.compiler.registry import _ACTIONS, _EVENTS

logger = logging.getLogger("client")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_KEY_FIELDS = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}
_ENV_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def _resolve_api_key(client_cfg: dict, provider: str, cli_api_key: str | None) -> str:
    """Resolve the API key from CLI flag, config, or env var."""
    key_field = _API_KEY_FIELDS[provider]
    env_var = _ENV_VARS[provider]

    key = cli_api_key or client_cfg.get(key_field) or os.environ.get(env_var)
    if not key:
        logger.error("No %s API key found. Set %s env var, pass --api-key, or add to config.",
                      provider, env_var)
        sys.exit(1)
    return key


def _create_provider(provider_name: str, base_url: str = ""):
    """Create and return the appropriate provider instance."""
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "openai":
        return OpenAIProvider(base_url)
    logger.error("Unknown provider '%s'. Supported: anthropic, openai", provider_name)
    sys.exit(1)


def _mcp_tools_to_provider(mcp_tools, provider) -> list[dict]:
    """Convert MCP tool objects to provider-specific tool format."""
    return provider.tools_to_provider_format(
        [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in mcp_tools
        ]
    )


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------


async def _agentic_loop(
    provider,
    client,
    session: ClientSession,
    provider_tools: list[dict],
    messages: list[dict],
    system_prompt: str,
    model: str,
) -> None:
    """Inner loop: call LLM, execute tools, feed results back, repeat."""
    iteration = 0
    while True:
        iteration += 1
        logger.info("--- iteration %d  messages=%d ---", iteration, len(messages))

        await provider.agentic_loop(
            client=client,
            session=session,
            provider_tools=provider_tools,
            messages=messages,
            system_prompt=system_prompt,
            model=model,
        )

        if not messages:
            break

        last_role = messages[-1].get("role", "")

        if last_role == "assistant":
            content = messages[-1].get("content", "")
            has_tools = False
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "text"):
                        print(f"\n{provider.name.capitalize()}> {block.text}")
                    if getattr(block, "type", None) == "tool_use":
                        has_tools = True
            elif isinstance(content, str):
                print(f"\n{provider.name.capitalize()}> {content}")

            if not has_tools:
                break

        elif last_role in ("tool", "user"):
            continue


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------


async def run_chat(
    config: dict,
    cli_api_key: str | None,
    cli_model: str | None,
    cli_provider: str | None,
    cli_base_url: str | None,
) -> None:
    """Main chat loop: spawn MCP server, discover tools, run REPL."""
    # Load DSL registry to generate dynamic system prompt
    load_all()
    system_prompt = generate_system_prompt(_ACTIONS, _EVENTS)
    logger.info("Generated system prompt with %d actions, %d events", len(_ACTIONS), len(_EVENTS))

    client_cfg = config["client"]
    provider_name = cli_provider or client_cfg.get("provider", "anthropic")
    base_url = cli_base_url or client_cfg.get("openai_base_url", "")
    provider = _create_provider(provider_name, base_url)

    api_key = _resolve_api_key(client_cfg, provider_name, cli_api_key)
    model = cli_model or client_cfg.get("model", provider.default_model)

    server_cmd = ["steeleagle-mcp-server"]
    if config.get("_config_path"):
        server_cmd.extend(["-c", config["_config_path"]])

    server_params = StdioServerParameters(command=server_cmd[0], args=server_cmd[1:])

    logger.info("Spawning server: %s", " ".join(server_cmd))
    logger.info("Provider: %s  Model: %s", provider_name, model)

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools_result = await session.list_tools()
        provider_tools = _mcp_tools_to_provider(tools_result.tools, provider)

        tool_names = [t.name for t in tools_result.tools]
        logger.info("Discovered %d tools: %s", len(tool_names), ", ".join(tool_names))

        logger.info("Connected. Discovered %d tools.", len(provider_tools))
        logger.info("Type your mission instructions (Ctrl+C or 'quit' to exit).")

        client = provider.create_client(api_key)
        messages: list[dict] = []

        while True:
            try:
                user_input = input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                logger.info("Exiting.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                logger.info("Exiting.")
                break

            messages.append({"role": "user", "content": user_input})

            try:
                await _agentic_loop(
                    provider, client, session,
                    provider_tools, messages, system_prompt, model,
                )
            except Exception:
                logger.exception("Agentic loop error")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cli() -> None:
    """CLI entry point for steeleagle-mcp-client."""
    setup_logging()
    parser = make_client_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    config["_config_path"] = args.config

    asyncio.run(
        run_chat(config, args.api_key, args.model, args.provider, args.base_url)
    )
