const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8100";

/**
 * Create a WebSocket connection to the voice endpoint.
 * Converts http(s) base URL to ws(s) automatically.
 */
export function createVoiceSocket(sessionId: string): WebSocket {
  const wsUrl = API_URL.replace(/^http/, "ws");
  return new WebSocket(`${wsUrl}/ws/voice?session_id=${encodeURIComponent(sessionId)}`);
}