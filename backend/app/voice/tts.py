"""Gemini TTS streaming client and sentence buffer for chunked TTS."""

import re
from typing import AsyncIterator

from google import genai
from google.genai import types

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
            # Only split if followed by space, newline, or end of string
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


_client: genai.Client | None = None


def _get_client(api_key: str) -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=api_key)
    return _client


async def stream_tts(text: str, api_key: str) -> AsyncIterator[bytes]:
    """Yield 24kHz 16-bit mono PCM audio for the given text in 4096-byte chunks."""
    client = _get_client(api_key)
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
