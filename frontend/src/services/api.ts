import type { ChatRequest, SSEEvent } from "../types/chat";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8100";

export async function streamChat(
  request: ChatRequest,
  onToken: (token: string) => void,
  onDone: (sources: string[]) => void,
  onError: (error: string) => void,
  onLimitReached: () => void
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    onError("unable to reach the server. please check your connection and try again.");
    return;
  }

  if (response.status === 429) {
    try {
      const body = await response.json();
      if (body.detail === "limit_reached") {
        onLimitReached();
        return;
      }
    } catch {
      // Nginx rate limit — no JSON body
    }
    onError("too many requests. please wait a moment and try again.");
    return;
  }

  if (response.status >= 500) {
    onError("the server encountered an error. please try again later.");
    return;
  }

  if (!response.ok) {
    onError("something went wrong. please try again.");
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError("Streaming not supported in this browser.");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;

      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const event: SSEEvent = JSON.parse(jsonStr);

        if ("error" in event) {
          onError(event.error);
          return;
        }

        if ("done" in event) {
          onDone(event.sources);
          return;
        }

        if ("token" in event) {
          onToken(event.token);
        }
      } catch {
        // Skip malformed JSON
      }
    }
  }
}
