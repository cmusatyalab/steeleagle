"""SSE chat endpoint for the Plan page GCS Assistant."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.chat_agent import iter_chat_events

logger = logging.getLogger("chat")

router = APIRouter(prefix="/api")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    draft_dsl: str | None = None


def _sse_pack(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
