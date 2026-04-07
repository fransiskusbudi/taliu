"""Deepgram Nova-3 live transcription client (deepgram-sdk v6)."""

import asyncio
import logging
from typing import Optional

from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.types import ListenV1Results

logger = logging.getLogger(__name__)


class DeepgramSTT:
    """Manages a Deepgram live transcription WebSocket for one call session."""

    def __init__(self, api_key: str):
        self._client = AsyncDeepgramClient(api_key=api_key)
        self._socket = None
        self._cm = None
        self._listen_task: Optional[asyncio.Task] = None
        self._transcript_queue: asyncio.Queue[str] = asyncio.Queue()

    async def start(self) -> None:
        """Open the Deepgram WebSocket and start the receive loop."""
        self._cm = self._client.listen.v1.connect(
            model="nova-3",
            encoding="linear16",
            sample_rate=16000,
            endpointing=600,
        )
        self._socket = await self._cm.__aenter__()
        self._listen_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        """Background task: read messages from Deepgram and queue final transcripts."""
        try:
            async for message in self._socket:
                if isinstance(message, ListenV1Results):
                    if message.speech_final:
                        transcript = message.channel.alternatives[0].transcript
                        if transcript and transcript.strip():
                            await self._transcript_queue.put(transcript)
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
