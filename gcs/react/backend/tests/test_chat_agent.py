from unittest.mock import patch

import pytest

from app.chat_agent import (
    dispatch_tool,
    load_client_settings,
    resolve_api_key,
    run_chat_turn,
)
from app.dsl_graph import init_dsl_parser, parse_dsl_to_graph


MINIMAL_DSL = """\
Actions:
    TakeOff take_off(take_off_altitude = 10.0)
    Land land()
Mission:
    Start take_off
    During take_off:
        done -> land
"""


@pytest.fixture(scope="module", autouse=True)
def dsl_parser():
    init_dsl_parser()


def test_resolve_api_key_prefers_config_then_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert resolve_api_key({"openai_api_key": "sk-from-config"}, "openai") == "sk-from-config"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    assert resolve_api_key({}, "openai") == "sk-from-env"
    assert resolve_api_key({"openai_api_key": ""}, "openai") == "sk-from-env"


def test_dispatch_unknown_tool():
    result = dispatch_tool("takeoff", {})
    assert result["ok"] is False


def test_parse_dsl_to_graph_minimal():
    graph = parse_dsl_to_graph(MINIMAL_DSL)
    assert graph["start_id"] == "take_off"
    assert len(graph["nodes"]) == 2
    assert any(e["event_id"] == "done" for e in graph["edges"])


def test_load_client_settings_reads_repo_config():
    settings = load_client_settings()
    assert settings["provider"] in {"openai", "anthropic"}
    assert settings["model"]


@pytest.mark.asyncio
async def test_run_chat_turn_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def fake_settings(_path=None):
        return {
            "config_path": "mcp/config.toml",
            "provider": "openai",
            "model": "gpt-4o",
            "base_url": "",
            "api_key": None,
        }

    with patch("app.chat_agent.load_client_settings", fake_settings):
        with pytest.raises(ValueError, match="No API key"):
            await run_chat_turn([{"role": "user", "content": "patrol area B"}])


@pytest.mark.asyncio
async def test_run_chat_turn_builds_artifact(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    async def fake_openai(settings, messages, system, tool_payloads, status):
        tool_payloads.append(
            {
                "ok": True,
                "normalized_dsl": MINIMAL_DSL,
                "mission_json": {"start_action_id": "take_off_1"},
                "compile_id": "compile-test",
                "errors": [],
            }
        )
        return "Here is a draft mission.\n```dsl\n...\n```"

    with patch("app.chat_agent._run_openai", fake_openai):
        with patch(
            "app.chat_agent.load_client_settings",
            return_value={
                "config_path": "mcp/config.toml",
                "provider": "openai",
                "model": "gpt-4o",
                "base_url": "",
                "api_key": "sk-test",
            },
        ):
            result = await run_chat_turn(
                [{"role": "user", "content": "take off then return home"}]
            )

    assert "draft" in result
    assert result["draft"]["normalized_dsl"]
    assert len(result["artifacts"]) == 1
    art = result["artifacts"][0]
    assert art["target"] == "fsm-builder"
    assert art["payload"]["start_id"] == "take_off"
    assert len(art["payload"]["nodes"]) == 2
