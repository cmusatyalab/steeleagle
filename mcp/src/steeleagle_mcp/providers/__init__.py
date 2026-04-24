# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""Base protocol and utility functions for LLM providers."""

from typing import Any, Protocol


class LLMProvider(Protocol):
    """Protocol for LLM provider implementations."""

    name: str
    default_model: str

    def create_client(self, api_key: str) -> Any:
        """Create and return an LLM client instance."""

    def tools_to_provider_format(self, mcp_tools: list[dict]) -> list[dict]:
        """Convert MCP tools to provider-specific tool format."""

    async def agentic_loop(
        self,
        client: Any,
        session: Any,
        provider_tools: list[dict],
        messages: list[dict],
        system_prompt: str,
        model: str,
    ) -> None:
        """Run the agentic loop with the provider's API."""

    def tool_call_to_id(self, tool_call: Any) -> str:
        """Extract tool call ID from a tool call object."""

    def tool_result_to_message(self, tool_call_id: str, content: str) -> dict[str, Any]:
        """Convert tool result to a message in provider format."""
