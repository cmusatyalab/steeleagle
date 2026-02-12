# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""Configuration loading and shared utilities for the MCP server and client."""

import argparse
import logging

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def setup_logging() -> None:
    """Configure rich-based logging for both server and client CLIs.

    All output goes to stderr so it never pollutes the MCP stdio protocol
    (which uses stdout for JSON-RPC).
    """
    import sys

    from rich.console import Console
    from rich.logging import RichHandler

    handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
    )

    # Remove the root logger's existing handlers (force=True),
    # and also clear handlers on any loggers that libraries already created.
    logging.root.handlers.clear()
    for name in list(logging.Logger.manager.loggerDict):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        force=True,
    )

    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "openai", "anthropic", "mcp.client", "mcp.server"):
        logging.getLogger(name).setLevel(logging.WARNING)


DEFAULT_DRONE_CONFIG = {
    "name": "drone0",
    "kernel": "unix:///tmp/kernel.sock",
    "telemetry": "ipc:///tmp/driver_telem.sock",
    "results": "ipc:///tmp/results.sock",
}

DEFAULT_COMPUTE_CONFIG = {
    "db_path": "mcp_mission.db",
}

DEFAULT_CLIENT_CONFIG = {
    "provider": "anthropic",
    "anthropic_api_key": "",
    "openai_api_key": "",
    "openai_base_url": "",
    "model": "claude-sonnet-4-20250514",
}

DEFAULT_PORT = 8080


def load_config(config_path: str | None) -> dict:
    """Load configuration from a TOML file, falling back to defaults."""
    if config_path:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
    else:
        raw = {}

    return {
        "drone": {**DEFAULT_DRONE_CONFIG, **raw.get("drone", {})},
        "compute": {**DEFAULT_COMPUTE_CONFIG, **raw.get("compute", {})},
        "client": {**DEFAULT_CLIENT_CONFIG, **raw.get("client", {})},
    }


def make_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steeleagle-mcp-server",
        description="MCP server for SteelEagle drone control",
    )
    parser.add_argument("-c", "--config", default=None, help="Path to TOML config file")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable_http"],
        default="stdio",
        help="Transport mode (stdio, sse, or streamable_http)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind for HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind for HTTP transport (default: 8080)",
    )
    return parser


def make_client_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steeleagle-mcp-client",
        description="MCP client REPL for SteelEagle drone control via LLM",
    )
    parser.add_argument("-c", "--config", default=None, help="Path to TOML config file")
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        default=None,
        help="LLM provider (anthropic or openai)",
    )
    parser.add_argument("--api-key", default=None, help="API key for the provider")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL for OpenAI-compatible services (e.g., http://localhost:8080/v1)",
    )
    parser.add_argument("--model", default=None, help="Model to use")
    return parser
