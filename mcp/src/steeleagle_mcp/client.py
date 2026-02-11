"""MCP Client: Interactive chat REPL for drone mission planning via Claude.

Spawns the MCP server as a subprocess (stdio transport), discovers tools,
and runs an agentic loop: user message → Claude API (with tools) → execute
tool_use calls via MCP → feed results back → repeat until done.
"""

import asyncio
import json
import logging
import os
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from steeleagle_mcp.config import load_config, make_client_parser
from steeleagle_mcp.system_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _resolve_api_key(client_cfg: dict, cli_api_key: str | None) -> str:
    """Resolve the Anthropic API key from CLI flag, config, or env var."""
    key = cli_api_key or client_cfg.get("anthropic_api_key") or os.environ.get(
        "ANTHROPIC_API_KEY"
    )
    if not key:
        print(
            "Error: No Anthropic API key found.\n"
            "Set ANTHROPIC_API_KEY env var, pass --api-key, or add to config file."
        )
        sys.exit(1)
    return key


def _mcp_tools_to_anthropic(mcp_tools) -> list[dict]:
    """Convert MCP tool objects to Anthropic API tool format."""
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


async def _agentic_loop(
    client: anthropic.Anthropic,
    session: ClientSession,
    model: str,
    anthropic_tools: list[dict],
    messages: list[dict],
    system_prompt: str = "",
) -> None:
    """Inner loop: call Claude, execute tools, feed results back, repeat."""
    while True:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt or SYSTEM_PROMPT,
            tools=anthropic_tools,
            messages=messages,
        )

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Print text blocks
        for block in assistant_content:
            if hasattr(block, "text"):
                print(f"\nClaude> {block.text}")

        # Collect tool_use blocks
        tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_use_blocks:
            break

        # Execute each tool call via MCP server
        tool_results = []
        for tb in tool_use_blocks:
            print(f"\n  [{tb.name}] args={json.dumps(tb.input)}")
            try:
                result = await session.call_tool(tb.name, tb.input)
                result_text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                # Show a truncated preview
                preview = result_text[:300]
                if len(result_text) > 300:
                    preview += "..."
                print(f"  [{tb.name}] result: {preview}")
            except Exception as e:
                result_text = json.dumps({"error": str(e)})
                print(f"  [{tb.name}] error: {e}")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": result_text,
                }
            )

        messages.append({"role": "user", "content": tool_results})


async def run_chat(config: dict, cli_api_key: str | None, cli_model: str | None) -> None:
    """Main chat loop: spawn MCP server, discover tools, run REPL."""
    client_cfg = config["client"]
    api_key = _resolve_api_key(client_cfg, cli_api_key)
    model = cli_model or client_cfg.get("model", "claude-sonnet-4-20250514")

    # Build server launch command
    server_cmd = ["steeleagle-mcp-server"]
    if config.get("_config_path"):
        server_cmd.extend(["-c", config["_config_path"]])

    server_params = StdioServerParameters(
        command=server_cmd[0],
        args=server_cmd[1:],
    )

    print(f"Starting MCP server: {' '.join(server_cmd)}")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools
            tools_result = await session.list_tools()
            anthropic_tools = _mcp_tools_to_anthropic(tools_result.tools)

            print(f"Connected. Discovered {len(anthropic_tools)} tools.")
            print(f"Model: {model}")
            print("Type your mission instructions (Ctrl+C or 'quit' to exit).\n")

            client = anthropic.Anthropic(api_key=api_key)
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
                        client, session, model, anthropic_tools, messages,
                    )
                except anthropic.APIError as e:
                    print(f"\nClaude API error: {e}")
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
    config["_config_path"] = args.config  # pass through for server subprocess

    asyncio.run(run_chat(config, args.api_key, args.model))
