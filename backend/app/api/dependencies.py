"""Shared dependencies for the API layer."""

from llama_index.core.chat_engine import CondensePlusContextChatEngine

from app.rag.engine import build_chat_engine

_chat_engine: CondensePlusContextChatEngine | None = None


def get_chat_engine() -> CondensePlusContextChatEngine:
    """Return a singleton chat engine instance."""
    global _chat_engine
    if _chat_engine is None:
        _chat_engine = build_chat_engine()
    return _chat_engine
