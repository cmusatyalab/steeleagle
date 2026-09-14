"""SSE chat endpoint for the Plan page GCS Assistant."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.chat_agent import iter_chat_events, load_client_settings

logger = logging.getLogger("chat")

router = APIRouter(prefix="/api")

_PROVIDER_LABELS = {
    "openai": "ChatGPT",
    "anthropic": "Claude",
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    draft_dsl: str | None = None


def _sse_pack(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/chat/status")
async def chat_status():
    """Indicates whether the current LLM provider has its API key set; not checking the key's functionality.
    The key itself is never returned. ``provider`` refers to the client provider in use (openai or anthropic); 
    while multiple keys can be present in the environment, only the chosen provider's key decides the ``configured`` status.
    """
    settings = load_client_settings()
    provider = settings["provider"]
    configured = bool(settings["api_key"])
    return {
        "configured": configured,
        "provider": provider,
        "model": settings["model"],
        "label": _PROVIDER_LABELS.get(provider, provider),
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
        if m.role in {"user", "assistant"} and (m.content or "").strip()
    ]
    draft_dsl = request.draft_dsl if request.draft_dsl else None

    async def event_stream():
        async for event, data in iter_chat_events(messages, draft_dsl):
            yield _sse_pack(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
