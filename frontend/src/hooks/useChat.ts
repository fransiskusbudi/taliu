import { useCallback, useRef, useState } from "react";
import { streamChat } from "../services/api";
import type { ChatMessage } from "../types/chat";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useRef(crypto.randomUUID());

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      setError(null);

      const userMessage: ChatMessage = { role: "user", content };
      setMessages((prev) => [...prev, userMessage]);

      // Add empty assistant message that will be filled by streaming
      const assistantMessage: ChatMessage = { role: "assistant", content: "" };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsStreaming(true);

      // Build conversation history (exclude the new messages we just added)
      const history = messages.slice();

      await streamChat(
        {
          message: content,
          session_id: sessionId.current,
          conversation_history: history,
        },
        // onToken
        (token) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                content: last.content + token,
              };
            }
            return updated;
          });
        },
        // onDone
        () => {
          setIsStreaming(false);
        },
        // onError
        (errorMsg) => {
          setError(errorMsg);
          setIsStreaming(false);
          // Remove the empty assistant message on error
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant" && last.content === "") {
              updated.pop();
            }
            return updated;
          });
        }
      );
    },
    [isStreaming, messages]
  );

  const resetChat = useCallback(() => {
    setMessages([]);
    setError(null);
    sessionId.current = crypto.randomUUID();
  }, []);

  return { messages, isStreaming, error, sendMessage, resetChat };
}
