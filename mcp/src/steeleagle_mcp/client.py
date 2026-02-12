"""MCP Client: Interactive chat REPL for drone mission planning via LLM providers.

Spawns the MCP server as a subprocess (stdio transport), discovers tools,
and runs an agentic loop: user message → LLM API (with tools) → execute
tool calls via MCP → feed results back → repeat until done.
"""

import asyncio
import logging
import os
import sys

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters
from steeleagle_mcp.config import load_config, make_client_parser
from steeleagle_mcp.providers.anthropic import AnthropicProvider
from steeleagle_mcp.providers.openai import OpenAIProvider
from steeleagle_mcp.system_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _resolve_api_key(client_cfg: dict, provider: str, cli_api_key: str | None) -> str:
    """Resolve the API key from CLI flag, config, or env var."""
    api_key_fields = {
        "anthropic": "anthropic_api_key",
        "openai": "openai_api_key",
    }
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    key_field = api_key_fields[provider]
    env_var = env_vars[provider]

    key = cli_api_key or client_cfg.get(key_field) or os.environ.get(env_var)
    if not key:
        print(
            f"Error: No {provider.capitalize()} API key found.\n"
            f"Set {env_var} env var, pass --api-key, or add to config file."
        )
        sys.exit(1)
    return key


def _create_provider(provider_name: str, base_url: str = ""):
    """Create and return the appropriate provider instance."""
    providers = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider(base_url)
        if provider_name == "openai"
        else OpenAIProvider(),
    }
    if provider_name not in providers:
        print(
            f"Error: Unknown provider '{provider_name}'. Supported: {', '.join(providers.keys())}"
        )
        sys.exit(1)
    return providers[provider_name]


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
    while True:
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


async def run_chat(
    config: dict,
    cli_api_key: str | None,
    cli_model: str | None,
    cli_provider: str | None,
    cli_base_url: str | None,
) -> None:
    """Main chat loop: spawn MCP server, discover tools, run REPL."""
    client_cfg = config["client"]
    provider_name = cli_provider or client_cfg.get("provider", "anthropic")
    base_url = cli_base_url or client_cfg.get("openai_base_url", "")
    provider = _create_provider(provider_name, base_url)

    api_key = _resolve_api_key(client_cfg, provider_name, cli_api_key)
    model = cli_model or client_cfg.get("model", provider.default_model)

    server_cmd = ["steeleagle-mcp-server"]
    if config.get("_config_path"):
        server_cmd.extend(["-c", config["_config_path"]])

    server_params = StdioServerParameters(
        command=server_cmd[0],
        args=server_cmd[1:],
    )

    print(f"Starting MCP server: {' '.join(server_cmd)}")
    print(f"Using provider: {provider_name}")
    print(f"Model: {model}")

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        tools_result = await session.list_tools()
        provider_tools = _mcp_tools_to_provider(tools_result.tools, provider)

        print(f"Connected. Discovered {len(provider_tools)} tools.")
        print("Type your mission instructions (Ctrl+C or 'quit' to exit).\n")

        client = provider.create_client(api_key)
        messages: list[dict] = []

        while True:
            try:
                user_input = input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                print("Exiting.")
                break

            messages.append({"role": "user", "content": user_input})

            try:
                await _agentic_loop(
                    provider,
                    client,
                    session,
                    provider_tools,
                    messages,
                    SYSTEM_PROMPT,
                    model,
                )
            except Exception as e:
                logger.exception("Error in agentic loop")
                print(f"\nError: {e}")


def cli() -> None:
    """CLI entry point for steeleagle-mcp-client."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    parser = make_client_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    config["_config_path"] = args.config

    asyncio.run(
        run_chat(config, args.api_key, args.model, args.provider, args.base_url)
    )
