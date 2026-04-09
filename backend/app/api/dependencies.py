"""Shared dependencies for the API layer."""

from llama_index.core.chat_engine import CondensePlusContextChatEngine, ContextChatEngine

from app.rag.engine import build_chat_engine, build_voice_chat_engine

_chat_engine: CondensePlusContextChatEngine | None = None
_voice_chat_engine: ContextChatEngine | None = None


def get_chat_engine() -> CondensePlusContextChatEngine:
    """Return a singleton chat engine instance."""
    global _chat_engine
    if _chat_engine is None:
        _chat_engine = build_chat_engine()
    return _chat_engine


def get_voice_chat_engine() -> ContextChatEngine:
    """Return a singleton voice chat engine (no condense step)."""
    global _voice_chat_engine
    if _voice_chat_engine is None:
        _voice_chat_engine = build_voice_chat_engine()
    return _voice_chat_engine
