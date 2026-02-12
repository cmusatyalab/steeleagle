# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""Anthropic provider implementation for MCP client."""

import logging
from typing import Any

from anthropic import Anthropic

from steeleagle_mcp.providers import LLMProvider

logger = logging.getLogger(__name__)


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
        """Run the agentic loop with Anthropic's API."""
        response = client.messages.create(
            model=model,
            messages=messages,
            system=system_prompt,
            tools=provider_tools,
            max_tokens=4096,
        )

        messages.append({"role": "assistant", "content": response.content})

        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_message = await _execute_tool(session, content_block)
                messages.append(tool_message)

    def tool_call_to_id(self, tool_call: Any) -> str:
        """Extract tool call ID from a tool_use block."""
        return tool_call.id

    def tool_result_to_message(self, tool_call_id: str, content: str) -> dict[str, Any]:
        """Convert tool result to an Anthropic tool result message."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": content,
                }
            ],
        }


async def _execute_tool(session: Any, tool_use_block: Any) -> dict[str, Any]:
    """Execute an MCP tool and return the result as a message."""
    tool_name = tool_use_block.name
    tool_input = tool_use_block.input

    logger.debug("Executing tool: %s", tool_name)

    result = await session.call_tool(tool_name, tool_input)
    result_text = (
        result.content[0].text if hasattr(result.content[0], "text") else str(result)
    )

    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_block.id,
                "content": result_text,
            }
        ],
    }
