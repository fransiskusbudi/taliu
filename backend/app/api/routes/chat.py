"""POST /api/chat — main chat endpoint with SSE streaming."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_chat_engine
from app.config import settings
from app.db.session import (
    get_or_create_session,
    check_limit,
    get_history,
    save_messages,
)
from app.models.chat import ChatRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/history/{session_id}")
async def history(session_id: str, http_request: Request):
    pool = http_request.app.state.db
    msgs = await get_history(pool, session_id)
    limit_reached = await check_limit(pool, session_id, settings.message_limit)
    return {
        "messages": [{"role": m.role, "content": m.content} for m in msgs],
        "limit_reached": limit_reached,
    }


@router.post("/chat")
async def chat(
    request: ChatRequest,
    http_request: Request,
    chat_engine: CondensePlusContextChatEngine = Depends(get_chat_engine),
):
    pool = http_request.app.state.db
    ip = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("user-agent", "")

    await get_or_create_session(pool, request.session_id, ip, user_agent)

    if await check_limit(pool, request.session_id, settings.message_limit):
        raise HTTPException(status_code=429, detail="limit_reached")

    history = await get_history(pool, request.session_id)

    # Load history into chat engine memory
    chat_engine.reset()
    for msg in history:
        role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
        chat_engine._memory.put(LlamaChatMessage(role=role, content=msg.content))

    async def event_generator():
        start_time = time.monotonic()
        full_response = ""

        try:
            streaming_response = await chat_engine.astream_chat(request.message)

            async for token in streaming_response.async_response_gen():
                full_response += token
                yield {"data": json.dumps({"token": token})}

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract token counts if available
            prompt_tokens = None
            completion_tokens = None
            if hasattr(streaming_response, "response_metadata"):
                meta = streaming_response.response_metadata
                prompt_tokens = meta.get("prompt_tokens")
                completion_tokens = meta.get("completion_tokens")

            await save_messages(
                pool=pool,
                session_id=request.session_id,
                user_content=request.message,
                assistant_content=full_response,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=settings.openai_model,
            )

            # Build sources list
            source_nodes = streaming_response.source_nodes
            sources = []
            for node in source_nodes:
                meta = node.metadata
                company = meta.get("company", "")
                role_name = meta.get("role", "")
                section = meta.get("section", "")
                if company and role_name:
                    sources.append(f"{company} - {role_name}")
                elif section:
                    sources.append(section)

            yield {"data": json.dumps({"done": True, "sources": sources})}

        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            yield {"data": json.dumps({"error": "Something went wrong. Please try again."})}

    return EventSourceResponse(event_generator())
