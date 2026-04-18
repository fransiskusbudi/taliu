"""TTS streaming clients (OpenAI + Gemini) and sentence buffer.

The active provider is selected via `settings.tts_provider` ("openai" | "gemini").
"""

import re
from typing import AsyncIterator

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from app.config import settings


class SentenceBuffer:
    """Accumulates LLM token stream and yields complete sentences for TTS."""

    def __init__(self, min_chars: int = 30):
        self._buf = ""
        self._min_chars = min_chars

    def feed(self, token: str) -> list[str]:
        """Add token to buffer. Return list of complete sentences (may be empty).

        Splitting begins only once the buffer reaches min_chars total length.
        Once that threshold is met, all sentence boundaries are flushed.
        """
        self._buf += token
        sentences = []
        if len(self._buf) < self._min_chars:
            return sentences
        while True:
            match = re.search(r"[.!?]", self._buf)
            if not match:
                break
            end = match.end()
            rest = self._buf[end:]
            if rest and rest[0] not in " \n":
                break
            sentences.append(self._buf[:end].strip())
            self._buf = rest.lstrip()
        return sentences

    def flush(self) -> str:
        """Return any remaining buffered text and clear the buffer."""
        remaining = self._buf.strip()
        self._buf = ""
        return remaining


# ---------- OpenAI TTS ----------

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def _stream_tts_openai(text: str) -> AsyncIterator[bytes]:
    """OpenAI tts-1 → PCM 24kHz 16-bit mono, true streaming via chunked transfer."""
    client = _get_openai_client()
    async with client.audio.speech.with_streaming_response.create(
        model=settings.openai_tts_model,
        voice=settings.openai_tts_voice,
        input=text,
        response_format="pcm",
    ) as response:
        async for chunk in response.iter_bytes(chunk_size=4096):
            yield chunk


# ---------- Gemini TTS ----------

_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


async def _stream_tts_gemini(text: str) -> AsyncIterator[bytes]:
    """Gemini Flash TTS → PCM 24kHz 16-bit mono."""
    client = _get_gemini_client()
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=settings.gemini_tts_voice,
                )
            )
        ),
    )

    stream = await client.aio.models.generate_content_stream(
        model=settings.gemini_tts_model,
        contents=text,
        config=config,
    )

    async for chunk in stream:
        if not chunk.candidates:
            continue
        parts = chunk.candidates[0].content.parts or []
        for part in parts:
            data = getattr(part.inline_data, "data", None) if part.inline_data else None
            if not data:
                continue
            for i in range(0, len(data), 4096):
                yield data[i : i + 4096]


# ---------- Dispatcher ----------


async def stream_tts(text: str) -> AsyncIterator[bytes]:
    """Yield 24kHz 16-bit mono PCM audio for the given text in 4096-byte chunks.

    Dispatches to the provider configured via `settings.tts_provider`.
    """
    provider = settings.tts_provider.lower()
    if provider == "openai":
        async for chunk in _stream_tts_openai(text):
            yield chunk
    elif provider == "gemini":
        async for chunk in _stream_tts_gemini(text):
            yield chunk
    else:
        raise ValueError(f"Unknown TTS provider: {provider!r}")
