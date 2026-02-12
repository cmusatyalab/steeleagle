# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""OpenAI provider implementation for MCP client."""

import logging
from typing import Any

from openai import OpenAI

from steeleagle_mcp.providers import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Provider implementation for OpenAI models."""

    name = "openai"
    default_model = "gpt-4o"

    def __init__(self, base_url: str = "") -> None:
        self._client_class = OpenAI
        self._base_url = base_url

    def create_client(self, api_key: str) -> OpenAI:
        """Create and return an OpenAI client instance."""
        if self._base_url:
            return self._client_class(api_key=api_key, base_url=self._base_url)
        return self._client_class(api_key=api_key)

    def tools_to_provider_format(self, mcp_tools: list[dict]) -> list[dict]:
        """Convert MCP tools to OpenAI tool format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in mcp_tools
        ]

    async def agentic_loop(
        self,
        client: OpenAI,
        session: Any,
        provider_tools: list[dict],
        messages: list[dict],
        system_prompt: str,
        model: str,
    ) -> None:
        """Run the agentic loop with OpenAI's API."""
        messages_with_system = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages_with_system,
            tools=provider_tools,
            max_tokens=4096,
        )

        choice = response.choices[0]
        message = choice.message
        messages.append({"role": "assistant", "content": message.content or ""})

        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_message = await _execute_tool(session, tool_call)
                messages.append(tool_message)

    def tool_call_to_id(self, tool_call: Any) -> str:
        """Extract tool call ID from an OpenAI tool call."""
        return tool_call.id

    def tool_result_to_message(self, tool_call_id: str, content: str) -> dict[str, Any]:
        """Convert tool result to an OpenAI tool message."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }


async def _execute_tool(session: Any, tool_call: Any) -> dict[str, Any]:
    """Execute an MCP tool and return the result as a message."""
    tool_name = tool_call.function.name
    tool_input = (
        tool_call.function.arguments
        if isinstance(tool_call.function.arguments, dict)
        else {}
    )

    logger.debug("Executing tool: %s", tool_name)

    result = await session.call_tool(tool_name, tool_input)
    result_text = (
        result.content[0].text if hasattr(result.content[0], "text") else str(result)
    )

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": result_text,
    }
