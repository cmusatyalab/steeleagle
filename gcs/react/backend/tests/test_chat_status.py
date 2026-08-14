from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import app


@pytest.mark.asyncio
async def test_chat_status_configured_openai():
    with patch(
        "app.chat.load_client_settings",
        return_value={
            "config_path": "mcp/config.toml",
            "provider": "openai",
            "model": "gpt-4o",
            "base_url": "",
            "api_key": "sk-test",
        },
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/chat/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["provider"] == "openai"
    assert data["label"] == "ChatGPT"
    assert data["model"] == "gpt-4o"
    assert "api_key" not in data


@pytest.mark.asyncio
async def test_chat_status_unconfigured_ignores_other_provider_key():
    # Only check the active provider's key is empty or not,
    # regardless of other providers' keys.
    with patch(
        "app.chat.load_client_settings",
        return_value={
            "config_path": "mcp/config.toml",
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "base_url": "",
            "api_key": None,
        },
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/chat/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["provider"] == "anthropic"
    assert data["label"] == "Claude"
