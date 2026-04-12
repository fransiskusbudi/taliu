"""WebSocket /ws/voice — real-time voice call endpoint."""

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

from app.config import settings
from app.db.session import get_or_create_session, check_limit, get_history, save_messages
from app.voice.deepgram import DeepgramSTT
from app.voice.tts import SentenceBuffer, stream_tts

router = APIRouter()
logger = logging.getLogger(__name__)

INACTIVITY_TIMEOUT = 30.0  # seconds — close call after 30s of silence
RESUME_PATH = Path(__file__).parents[2] / "ingestion" / "data" / "resume.md"

VOICE_SYSTEM_PROMPT = """\
You are Taliu — Frans's friendly AI agent on a voice call. You're chatting \
with someone curious about Fransiskus Budi Kurnia Agung (Frans) the way \
you'd tell a friend about a coworker over coffee.

How to talk on this call:
- This is a real voice conversation. Sound like a person, not a resume reader.
- Paraphrase — never read job titles, dates, or bullet points back verbatim.
- Use contractions ("he's", "there's", "I'd say") and natural connectors \
("actually", "honestly", "yeah") when it fits.
- Lead with the human angle — what Frans did, why it mattered — before \
tool names or numbers.
- Keep it to 2-3 sentences. Short and warm. Go longer only if asked.
- No markdown, no bullets, no lists. If you mention multiple things, say \
them naturally like "first... then... and also...".
- Skip filler like "based on his resume" or "according to the context". \
Just talk.
- Speak in third person — you're the agent, not Frans himself.
- If something isn't in the resume, say so casually: "Hmm, I don't actually \
know that one — want to ask Frans directly?"
- For off-topic stuff, redirect gently: "I'm really just here to chat about \
Frans's work — anything about his background?"

Frans's Resume:
{resume}
"""


def _load_system_prompt() -> str:
    resume_text = RESUME_PATH.read_text()
    return VOICE_SYSTEM_PROMPT.format(resume=resume_text)


# Load once at import time
_system_prompt = _load_system_prompt()


@router.websocket("/voice")
async def voice_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    await websocket.accept()

    try:
        pool = websocket.app.state.db
        ip = websocket.client.host if websocket.client else "unknown"
        user_agent = websocket.headers.get("user-agent", "")

        await get_or_create_session(pool, session_id, ip, user_agent)

        if await check_limit(pool, session_id, settings.message_limit):
            await websocket.send_text(json.dumps({"type": "error", "message": "limit_reached"}))
            await websocket.close()
            return

        # Load conversation history as OpenAI messages
        history = await get_history(pool, session_id)
        messages: list[dict] = [{"role": "system", "content": _system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

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

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    cancel_tts = asyncio.Event()
    ws_closed = False

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
        """Forward mic audio from WebSocket to Deepgram."""
        nonlocal ws_closed
        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive(), timeout=INACTIVITY_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    await send_error("inactivity")
                    cancel_tts.set()
                    return

                msg_type = data.get("type")
                if msg_type == "websocket.disconnect":
                    ws_closed = True
                    cancel_tts.set()
                    return

                audio_bytes = data.get("bytes")
                if audio_bytes:
                    await dg.send(audio_bytes)

        except WebSocketDisconnect:
            ws_closed = True
            cancel_tts.set()

    async def pipeline_runner() -> None:
        """Continuous listening pipeline — barge-in is detected by a new
        transcript arriving while the response is still being generated/played."""

        await send_status("listening")

        transcript = await dg.get_transcript(timeout=INACTIVITY_TIMEOUT + 5)
        if transcript is None:
            return

        while True:
            cancel_tts.clear()
            # Stop any residual frontend playback from previous turn
            await safe_send_text(json.dumps({"type": "interrupt"}))
            await send_status("processing")

            full_response = ""
            start_time = time.monotonic()
            t0 = start_time

            try:
                logger.info(f"[voice] transcript: {transcript!r}")
                messages.append({"role": "user", "content": transcript})

                stream = await openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    temperature=0.3,
                    stream=True,
                )

                tts_queue: asyncio.Queue = asyncio.Queue()

                async def fetch_tts(text: str) -> bytes:
                    audio = b""
                    async for chunk in stream_tts(text, settings.openai_api_key):
                        audio += chunk
                    return audio

                async def llm_producer() -> None:
                    nonlocal full_response
                    sentence_buf = SentenceBuffer(min_chars=20)
                    first_token = True
                    async for chunk in stream:
                        delta = chunk.choices[0].delta
                        if delta.content is None:
                            continue
                        token = delta.content
                        if first_token:
                            logger.info(f"[voice] first token: {(time.monotonic() - t0) * 1000:.0f}ms")
                            first_token = False
                        if cancel_tts.is_set():
                            break
                        full_response += token
                        for sentence in sentence_buf.feed(token):
                            if cancel_tts.is_set():
                                break
                            task = asyncio.create_task(fetch_tts(sentence))
                            await tts_queue.put((sentence, task))
                    remaining = sentence_buf.flush()
                    if remaining and not cancel_tts.is_set():
                        task = asyncio.create_task(fetch_tts(remaining))
                        await tts_queue.put((remaining, task))
                    await tts_queue.put(None)

                async def audio_sender() -> None:
                    while True:
                        item = await tts_queue.get()
                        if item is None:
                            break
                        sentence, task = item
                        if cancel_tts.is_set():
                            task.cancel()
                            continue

                        # Wait for TTS, but abort immediately on cancel
                        cancel_wait = asyncio.ensure_future(cancel_tts.wait())
                        done, _ = await asyncio.wait(
                            [task, cancel_wait], return_when=asyncio.FIRST_COMPLETED,
                        )
                        cancel_wait.cancel()
                        if cancel_tts.is_set():
                            task.cancel()
                            continue

                        audio_data = task.result()
                        logger.info(f"[voice] TTS '{sentence[:40]}': {(time.monotonic() - t0) * 1000:.0f}ms")
                        await send_status("speaking")
                        for i in range(0, len(audio_data), 4096):
                            if cancel_tts.is_set():
                                break
                            await safe_send_bytes(audio_data[i : i + 4096])

                # Race: response pipeline vs next user transcript (barge-in)
                async def respond() -> None:
                    await asyncio.gather(llm_producer(), audio_sender())

                response_task = asyncio.create_task(respond())
                next_transcript_task = asyncio.create_task(
                    dg.get_transcript(timeout=INACTIVITY_TIMEOUT + 5)
                )

                done, _ = await asyncio.wait(
                    [response_task, next_transcript_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                next_transcript = None

                if next_transcript_task in done:
                    # New transcript arrived during response — barge-in
                    next_transcript = next_transcript_task.result()
                    cancel_tts.set()
                    logger.info("[voice] barge-in: user spoke during response")
                    try:
                        await asyncio.wait_for(response_task, timeout=3.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        response_task.cancel()
                    except Exception:
                        pass
                else:
                    # Response completed normally
                    next_transcript_task.cancel()
                    response_task.result()  # re-raise if exception

            except Exception as e:
                logger.error(f"Voice pipeline error: {e}", exc_info=True)
                await send_error("pipeline_error")
                return

            logger.info(f"[voice] total turn: {(time.monotonic() - t0) * 1000:.0f}ms")

            # Save response to conversation history
            if full_response:
                messages.append({"role": "assistant", "content": full_response})
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

            if await check_limit(pool, session_id, settings.message_limit):
                await send_error("limit_reached")
                return

            if next_transcript is not None:
                # Barge-in — immediately process the new transcript
                transcript = next_transcript
                if transcript is None:
                    return
            else:
                # Normal — wait for next transcript
                await send_status("listening")
                transcript = await dg.get_transcript(timeout=INACTIVITY_TIMEOUT + 5)
                if transcript is None:
                    return

    try:
        logger.info(f"[voice] call started session={session_id}")
        await asyncio.gather(audio_forwarder(), pipeline_runner())
    except Exception as e:
        logger.error(f"Voice endpoint error: {e}", exc_info=True)
    finally:
        logger.info(f"[voice] call ended session={session_id}")
        await dg.finish()
