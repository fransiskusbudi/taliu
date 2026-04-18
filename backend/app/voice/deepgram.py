"""Deepgram Nova-3 live transcription client (deepgram-sdk v6)."""

import asyncio
import logging
from typing import Optional

from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.types import (
    ListenV1Results,
    ListenV1UtteranceEnd,
)

from app.config import settings

logger = logging.getLogger(__name__)


class DeepgramSTT:
    """Manages a Deepgram live transcription WebSocket for one call session."""

    def __init__(self, api_key: str):
        self._client = AsyncDeepgramClient(api_key=api_key)
        self._socket = None
        self._cm = None
        self._listen_task: Optional[asyncio.Task] = None
        self._transcript_queue: asyncio.Queue[str] = asyncio.Queue()
        # Buffer of is_final=True segments awaiting utterance boundary
        self._pending_segments: list[str] = []

    async def start(self) -> None:
        """Open the Deepgram WebSocket and start the receive loop."""
        self._cm = self._client.listen.v1.connect(
            model="nova-3",
            encoding="linear16",
            sample_rate=16000,
            endpointing=settings.deepgram_endpointing_ms,
            interim_results=True,
            utterance_end_ms=settings.deepgram_utterance_end_ms,
        )
        self._socket = await self._cm.__aenter__()
        self._listen_task = asyncio.create_task(self._receive_loop())

    def _flush_pending(self, reason: str) -> Optional[str]:
        """Join and clear pending segments. Returns the joined transcript or None."""
        if not self._pending_segments:
            return None
        full = " ".join(self._pending_segments).strip()
        self._pending_segments = []
        if full:
            logger.info(f"[dg] flush ({reason}): {full!r}")
            return full
        return None

    async def _receive_loop(self) -> None:
        """Background task: read messages from Deepgram and queue final transcripts."""
        try:
            async for message in self._socket:
                if isinstance(message, ListenV1Results):
                    transcript = message.channel.alternatives[0].transcript
                    is_final = getattr(message, "is_final", False)
                    speech_final = getattr(message, "speech_final", False)

                    if transcript and transcript.strip():
                        logger.info(
                            f"[dg] transcript={transcript!r} "
                            f"is_final={is_final} speech_final={speech_final}"
                        )
                        if is_final:
                            self._pending_segments.append(transcript.strip())
                        if speech_final:
                            flushed = self._flush_pending("speech_final")
                            if flushed:
                                await self._transcript_queue.put(flushed)

                elif isinstance(message, ListenV1UtteranceEnd):
                    flushed = self._flush_pending("utterance_end")
                    if flushed:
                        await self._transcript_queue.put(flushed)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Deepgram receive loop error: {e}")

    async def send(self, audio_chunk: bytes) -> None:
        """Forward raw PCM audio bytes to Deepgram."""
        if self._socket:
            await self._socket.send_media(audio_chunk)

    async def get_transcript(self, timeout: float = 35.0) -> str | None:
        """Wait for a final transcript. Returns None if timeout expires."""
        try:
            return await asyncio.wait_for(self._transcript_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def finish(self) -> None:
        """Close the Deepgram WebSocket and stop the receive loop."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._socket:
            try:
                await self._socket.send_close_stream()
            except Exception:
                pass
        if self._cm:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
