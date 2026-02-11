"""Configuration loading for the MCP server and client."""

import argparse
import os

try:
    import tomllib
except ImportError:
    import tomli as tomllib


DEFAULT_DRONE_CONFIG = {
    "name": "drone0",
    "kernel": "unix:///tmp/kernel.sock",
    "telemetry": "ipc:///tmp/driver_telem.sock",
    "results": "ipc:///tmp/results.sock",
}

DEFAULT_CPT_CONFIG = {
    "db_path": "mcp_mission.db",
}

DEFAULT_CLIENT_CONFIG = {
    "anthropic_api_key": "",
    "model": "claude-sonnet-4-20250514",
}


def load_config(config_path: str | None) -> dict:
    """Load configuration from a TOML file, falling back to defaults."""
    if config_path:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
    else:
        raw = {}

    return {
        "drone": {**DEFAULT_DRONE_CONFIG, **raw.get("drone", {})},
        "compute": {**DEFAULT_CPT_CONFIG, **raw.get("compute", {})},
        "client": {**DEFAULT_CLIENT_CONFIG, **raw.get("client", {})},
    }


def make_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steeleagle-mcp-server",
        description="MCP server for SteelEagle drone control",
    )
    parser.add_argument(
        "-c", "--config", default=None, help="Path to TOML config file"
    )
    return parser


def make_client_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steeleagle-mcp-client",
        description="MCP client REPL for SteelEagle drone control via Claude",
    )
    parser.add_argument(
        "-c", "--config", default=None, help="Path to TOML config file"
    )
    parser.add_argument(
        "--api-key", default=None, help="Anthropic API key (overrides config/env)"
    )
    parser.add_argument(
        "--model", default=None, help="Claude model to use"
    )
    return parser
