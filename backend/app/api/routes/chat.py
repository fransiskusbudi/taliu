"""POST /api/chat — main chat endpoint with SSE streaming."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_chat_engine
from app.models.chat import ChatRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    chat_engine: CondensePlusContextChatEngine = Depends(get_chat_engine),
):
    # Load conversation history into the engine's memory
    chat_engine.reset()
    for msg in request.conversation_history:
        role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
        chat_engine._memory.put(LlamaChatMessage(role=role, content=msg.content))

    async def event_generator():
        try:
            streaming_response = await chat_engine.astream_chat(request.message)

            async for token in streaming_response.async_response_gen():
                yield {"data": json.dumps({"token": token})}

            # Signal completion with source metadata
            source_nodes = streaming_response.source_nodes
            sources = []
            for node in source_nodes:
                meta = node.metadata
                company = meta.get("company", "")
                role = meta.get("role", "")
                section = meta.get("section", "")
                if company and role:
                    sources.append(f"{company} - {role}")
                elif section:
                    sources.append(section)

            yield {"data": json.dumps({"done": True, "sources": sources})}

        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            yield {
                "data": json.dumps(
                    {"error": "Something went wrong. Please try again."}
                )
            }

    return EventSourceResponse(event_generator())
