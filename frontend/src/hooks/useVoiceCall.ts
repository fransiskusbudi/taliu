import { useCallback, useRef, useState } from "react";
import { createVoiceSocket } from "../services/voiceApi";

export type VoiceStatus = "idle" | "listening" | "processing" | "speaking" | "error";

interface VoiceCallControls {
  status: VoiceStatus;
  errorMessage: string | null;
  startCall: (sessionId: string) => Promise<void>;
  endCall: () => void;
}

/**
 * Manages the full lifecycle of a voice call:
 * - Requests mic permission
 * - Opens AudioContext at 16kHz and loads the AudioWorklet processor
 * - Streams PCM mic audio to the backend via WebSocket
 * - Receives PCM TTS audio from backend and plays it via Web Audio API
 * - Drives status state from incoming JSON frames
 */
export function useVoiceCall(onLimitReached: () => void): VoiceCallControls {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const micCtxRef = useRef<AudioContext | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const [isSpeaking, setIsSpeaking] = useState(false);

  const cleanup = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;

    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;

    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current = null;

    micCtxRef.current?.close();
    micCtxRef.current = null;

    playCtxRef.current?.close();
    playCtxRef.current = null;

    nextPlayTimeRef.current = 0;
    setStatus("idle");
  }, []);

  const stopPlayback = useCallback(() => {
    activeSourcesRef.current.forEach((src) => {
      try { src.stop(); } catch { /* already stopped */ }
    });
    activeSourcesRef.current.clear();
    nextPlayTimeRef.current = 0;
    setIsSpeaking(false);
  }, []);

  /**
   * Schedule a chunk of 24kHz 16-bit mono PCM audio for playback.
   * Uses the AudioContext clock to queue chunks seamlessly.
   */
  const schedulePCMChunk = useCallback((pcmBuffer: ArrayBuffer) => {
    const ctx = playCtxRef.current;
    if (!ctx) return;
    if (ctx.state === "suspended") ctx.resume();

    const int16 = new Int16Array(pcmBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32767;
    }

    const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
    audioBuffer.copyToChannel(float32, 0);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    source.onended = () => {
      activeSourcesRef.current.delete(source);
      if (activeSourcesRef.current.size === 0) {
        setIsSpeaking(false);
      }
    };
    activeSourcesRef.current.add(source);
    setIsSpeaking(true);

    const startTime = Math.max(ctx.currentTime, nextPlayTimeRef.current);
    source.start(startTime);
    nextPlayTimeRef.current = startTime + audioBuffer.duration;
  }, []);

  const startCall = useCallback(async (sessionId: string) => {
    setErrorMessage(null);

    // Request microphone permission
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
    } catch {
      setErrorMessage("Microphone access is required to call Taliu.");
      return;
    }
    micStreamRef.current = stream;

    // Separate AudioContexts: 16kHz for mic capture, default rate for playback
    const micCtx = new AudioContext({ sampleRate: 16000 });
    micCtxRef.current = micCtx;

    const playCtx = new AudioContext();
    playCtxRef.current = playCtx;

    // Load and connect the AudioWorklet processor
    await micCtx.audioWorklet.addModule("/audio-processor.js");
    const source = micCtx.createMediaStreamSource(stream);
    const workletNode = new AudioWorkletNode(micCtx, "mic-processor");
    workletNodeRef.current = workletNode;

    // Open WebSocket
    const ws = createVoiceSocket(sessionId);
    wsRef.current = ws;

    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      // Start forwarding mic audio to the backend
      workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };
      source.connect(workletNode);
      // Connect worklet to a silent gain node (gain=0) — required to keep the
      // worklet processing without feeding mic audio back through the speakers
      const silentGain = micCtx.createGain();
      silentGain.gain.value = 0;
      workletNode.connect(silentGain);
      silentGain.connect(micCtx.destination);
    };

    ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary frame = TTS PCM audio chunk
        schedulePCMChunk(event.data);
      } else if (typeof event.data === "string") {
        // Text frame = status or error
        try {
          const msg = JSON.parse(event.data) as
            | { type: "status"; value: VoiceStatus }
            | { type: "error"; message: string }
            | { type: "interrupt" };

          if (msg.type === "interrupt") {
            stopPlayback();
          } else if (msg.type === "status") {
            setStatus(msg.value);
          } else if (msg.type === "error") {
            if (msg.message === "limit_reached") {
              onLimitReached();
            } else if (msg.message === "inactivity") {
              setErrorMessage("Call ended due to inactivity.");
            } else {
              setErrorMessage("Something went wrong. Please try again.");
            }
            cleanup();
          }
        } catch {
          // Ignore malformed frames
        }
      }
    };

    ws.onerror = () => {
      setErrorMessage("Couldn't connect. Please try again.");
      cleanup();
    };

    ws.onclose = () => {
      // Unexpected close (not triggered by our own cleanup)
      if (wsRef.current !== null) {
        setErrorMessage("Call disconnected.");
        cleanup();
      }
    };
  }, [cleanup, schedulePCMChunk, stopPlayback, onLimitReached]);

  const endCall = useCallback(() => {
    cleanup();
  }, [cleanup]);

  const effectiveStatus: VoiceStatus = isSpeaking && status === "listening" ? "speaking" : status;

  return { status: effectiveStatus, errorMessage, startCall, endCall };
}