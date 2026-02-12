# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""Anthropic provider implementation for MCP client."""

import logging
from typing import Any

from anthropic import Anthropic

from steeleagle_mcp.providers import LLMProvider

logger = logging.getLogger("provider.anthropic")


class AnthropicProvider(LLMProvider):
    """Provider implementation for Anthropic's Claude models."""

    name = "anthropic"
    default_model = "claude-sonnet-4-20250514"

    def __init__(self) -> None:
        self._client_class = Anthropic

    def create_client(self, api_key: str) -> Anthropic:
        """Create and return an Anthropic client instance."""
        return self._client_class(api_key=api_key)

    def tools_to_provider_format(self, mcp_tools: list[dict]) -> list[dict]:
        """Convert MCP tools to Anthropic tool format."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
            for tool in mcp_tools
        ]

    async def agentic_loop(
        self,
        client: Anthropic,
        session: Any,
        provider_tools: list[dict],
        messages: list[dict],
        system_prompt: str,
        model: str,
    ) -> None:
        """Run one LLM turn: send messages, execute any tool calls."""
        logger.info("LLM request  model=%s messages=%d", model, len(messages))
        response = client.messages.create(
            model=model,
            messages=messages,
            system=system_prompt,
            tools=provider_tools,
            max_tokens=4096,
        )

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]
        logger.info("LLM response  stop=%s tools=%d content=%s",
                 response.stop_reason, len(tool_blocks),
                 (text_blocks[0].text[:120] if text_blocks else ""))

        messages.append({"role": "assistant", "content": response.content})

        for i, block in enumerate(tool_blocks):
            logger.info("tool [%d/%d] %s(%s)", i + 1, len(tool_blocks),
                     block.name, block.input)
            result = await _execute_tool(session, block)
            logger.info("tool [%d/%d] %s -> %s", i + 1, len(tool_blocks),
                     block.name, result["content"][0]["content"][:120]
                     if isinstance(result["content"], list) else str(result["content"])[:120])
            messages.append(result)

    def tool_call_to_id(self, tool_call: Any) -> str:
        """Extract tool call ID from a tool_use block."""
        return tool_call.id

    def tool_result_to_message(self, tool_call_id: str, content: str) -> dict[str, Any]:
        """Convert tool result to an Anthropic tool result message."""
        return {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_call_id, "content": content}
            ],
        }


async def _execute_tool(session: Any, tool_use_block: Any) -> dict[str, Any]:
    """Execute an MCP tool and return the result as a message."""
    name = tool_use_block.name
    args = tool_use_block.input

    try:
        result = await session.call_tool(name, args)
    except Exception:
        logger.exception("MCP call failed: %s", name)
        raise

    if result.isError:
        logger.error("MCP error: %s  %s", name, result.content)

    text = result.content[0].text if hasattr(result.content[0], "text") else str(result)
    return {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": tool_use_block.id, "content": text}
        ],
    }
