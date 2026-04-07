"""WebSocket /ws/voice — real-time voice call endpoint."""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

from app.api.dependencies import get_chat_engine
from app.config import settings
from app.db.session import get_or_create_session, check_limit, get_history, save_messages
from app.voice.deepgram import DeepgramSTT
from app.voice.tts import SentenceBuffer, stream_tts

router = APIRouter()
logger = logging.getLogger(__name__)

INACTIVITY_TIMEOUT = 30.0  # seconds — close call after 30s of silence

VOICE_INSTRUCTION = (
    "[This is a voice conversation — respond in plain spoken language. "
    "No markdown, no bullet points, no headers, no bold/italic. "
    "Keep answers brief (2-3 sentences). Speak naturally as if on a phone call.]\n\n"
)


@router.websocket("/voice")
async def voice_endpoint(
    websocket: WebSocket,
    session_id: str,
    chat_engine: CondensePlusContextChatEngine = Depends(get_chat_engine),
):
    await websocket.accept()

    try:
        pool = websocket.app.state.db
        ip = websocket.client.host if websocket.client else "unknown"
        user_agent = websocket.headers.get("user-agent", "")

        await get_or_create_session(pool, session_id, ip, user_agent)

        # Check message limit before starting
        if await check_limit(pool, session_id, settings.message_limit):
            await websocket.send_text(json.dumps({"type": "error", "message": "limit_reached"}))
            await websocket.close()
            return

        # Load session history into chat engine memory
        history = await get_history(pool, session_id)
        chat_engine.reset()
        for msg in history:
            role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
            chat_engine._memory.put(LlamaChatMessage(role=role, content=msg.content))

        dg = DeepgramSTT(settings.deepgram_api_key)
        await dg.start()
    except Exception as e:
        logger.error(f"[voice] setup failed: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": "setup_failed"}))
            await websocket.close()
        except Exception:
            pass
        return

    # Set by audio_forwarder when audio arrives while TTS is playing
    cancel_tts = asyncio.Event()
    ws_closed = False
    is_speaking = False

    async def safe_send_text(data: str) -> None:
        if not ws_closed:
            try:
                await websocket.send_text(data)
            except Exception:
                pass

    async def safe_send_bytes(data: bytes) -> None:
        if not ws_closed:
            try:
                await websocket.send_bytes(data)
            except Exception:
                pass

    async def send_status(value: str) -> None:
        await safe_send_text(json.dumps({"type": "status", "value": value}))

    async def send_error(message: str) -> None:
        await safe_send_text(json.dumps({"type": "error", "message": message}))

    async def audio_forwarder() -> None:
        """Read audio binary frames from the WebSocket and forward to Deepgram."""
        nonlocal is_speaking, ws_closed
        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive(), timeout=INACTIVITY_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    await send_error("inactivity")
                    return

                msg_type = data.get("type")
                if msg_type == "websocket.disconnect":
                    ws_closed = True
                    cancel_tts.set()
                    return

                if data.get("bytes"):
                    # TODO: add barge-in with voice activity detection
                    await dg.send(data["bytes"])

        except WebSocketDisconnect:
            ws_closed = True
            cancel_tts.set()

    async def pipeline_runner() -> None:
        """Wait for transcripts from Deepgram, run RAG + TTS pipeline per turn."""
        nonlocal is_speaking

        await send_status("listening")

        while True:
            transcript = await dg.get_transcript(timeout=INACTIVITY_TIMEOUT + 5)
            if transcript is None:
                return  # Timeout — audio_forwarder will have sent inactivity error

            # New turn: clear any previous cancellation
            cancel_tts.clear()

            await send_status("processing")

            full_response = ""
            start_time = time.monotonic()

            try:
                t0 = time.monotonic()
                logger.info(f"[voice] got transcript: {transcript!r}")
                streaming_response = await chat_engine.astream_chat(
                    VOICE_INSTRUCTION + transcript
                )
                logger.info(f"[voice] RAG + LLM stream init: {(time.monotonic() - t0) * 1000:.0f}ms")
                sentence_buf = SentenceBuffer(min_chars=30)
                first_token = True

                async for token in streaming_response.async_response_gen():
                    if first_token:
                        logger.info(f"[voice] LLM first token: {(time.monotonic() - t0) * 1000:.0f}ms")
                        first_token = False
                    if cancel_tts.is_set():
                        break
                    full_response += token
                    sentences = sentence_buf.feed(token)
                    for sentence in sentences:
                        if cancel_tts.is_set():
                            break
                        is_speaking = True
                        await send_status("speaking")
                        tts_start = time.monotonic()
                        async for audio_chunk in stream_tts(sentence, settings.openai_api_key):
                            if cancel_tts.is_set():
                                break
                            await safe_send_bytes(audio_chunk)
                        logger.info(f"[voice] TTS '{sentence[:40]}': {(time.monotonic() - tts_start) * 1000:.0f}ms")

                # Flush any remaining buffered text
                if not cancel_tts.is_set():
                    remaining = sentence_buf.flush()
                    if remaining:
                        is_speaking = True
                        await send_status("speaking")
                        tts_start = time.monotonic()
                        async for audio_chunk in stream_tts(remaining, settings.openai_api_key):
                            if cancel_tts.is_set():
                                break
                            await safe_send_bytes(audio_chunk)
                        logger.info(f"[voice] TTS flush '{remaining[:40]}': {(time.monotonic() - tts_start) * 1000:.0f}ms")

                logger.info(f"[voice] total turn: {(time.monotonic() - t0) * 1000:.0f}ms")

            except Exception as e:
                logger.error(f"Voice pipeline error: {e}", exc_info=True)
                await send_error("pipeline_error")
                return
            finally:
                is_speaking = False

            # Persist the turn to the database
            if full_response:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                await save_messages(
                    pool=pool,
                    session_id=session_id,
                    user_content=transcript,
                    assistant_content=full_response,
                    latency_ms=latency_ms,
                    prompt_tokens=None,
                    completion_tokens=None,
                    model=settings.openai_model,
                )

            # Check limit after saving
            if await check_limit(pool, session_id, settings.message_limit):
                await send_error("limit_reached")
                return

            await send_status("listening")

    try:
        logger.info(f"[voice] call started session={session_id}")
        await asyncio.gather(audio_forwarder(), pipeline_runner())
    except Exception as e:
        logger.error(f"Voice endpoint error: {e}", exc_info=True)
    finally:
        logger.info(f"[voice] call ended session={session_id}")
        await dg.finish()
