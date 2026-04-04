export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  session_id: string;
  conversation_history: ChatMessage[];
}

export interface SSETokenEvent {
  token: string;
}

export interface SSEDoneEvent {
  done: true;
  sources: string[];
}

export interface SSEErrorEvent {
  error: string;
}

export type SSEEvent = SSETokenEvent | SSEDoneEvent | SSEErrorEvent;
