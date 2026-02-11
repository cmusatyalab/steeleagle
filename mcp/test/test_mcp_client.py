"""
Manual MCP test client for SteelEagle.

- Launches MCP server subprocess
- Lists tools
- Lets you manually call tools with JSON args
- Prints results
"""

import asyncio
import json
import sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


SERVER = StdioServerParameters(
    command="uv",
    args=[
        "run",
        "steeleagle-mcp-server",
        "--config",
        "config.toml",
    ],
)


async def interactive():
    print("Starting MCP server...")
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP session initialized.\n")

            while True:
                tools = await session.list_tools()
                tool_list = tools.tools

                print("\nAvailable tools:")
                for i, t in enumerate(tool_list):
                    print(f"{i:3d} | {t.name}")

                print("\nType tool number or name to call.")
                print("Type 'q' to quit.\n")

                choice = input("> ").strip()
                if choice.lower() in {"q", "quit", "exit"}:
                    print("Exiting.")
                    return

                # Determine tool name
                if choice.isdigit():
                    idx = int(choice)
                    if idx < 0 or idx >= len(tool_list):
                        print("Invalid index.")
                        continue
                    tool_name = tool_list[idx].name
                else:
                    tool_name = choice

                print(f"\nSelected tool: {tool_name}")
                print("Enter JSON arguments (or leave empty for {}):")

                raw_args = input("args> ").strip()
                if not raw_args:
                    args = {}
                else:
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError as e:
                        print("Invalid JSON:", e)
                        continue

                try:
                    result = await session.call_tool(tool_name, args)
                    print("\n=== TOOL RESULT ===")
                    try:
                        # Pretty-print JSON result if possible
                        parsed = json.loads(result.content[0].text)
                        print(json.dumps(parsed, indent=2))
                    except Exception:
                        print(result)
                    print("===================\n")

                except Exception as e:
                    print("Tool call failed:", e)


def main():
    try:
        asyncio.run(interactive())
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
