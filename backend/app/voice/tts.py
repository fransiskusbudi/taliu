"""OpenAI TTS streaming client and sentence buffer for chunked TTS."""

import re
from typing import AsyncIterator

from openai import AsyncOpenAI


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


async def stream_tts(text: str, api_key: str) -> AsyncIterator[bytes]:
    """Stream 24kHz 16-bit mono PCM audio chunks for the given text."""
    client = AsyncOpenAI(api_key=api_key)
    async with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=text,
        response_format="pcm",
    ) as response:
        async for chunk in response.iter_bytes(chunk_size=4096):
            yield chunk
