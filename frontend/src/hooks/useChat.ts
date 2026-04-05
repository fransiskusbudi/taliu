import { useCallback, useRef, useState } from "react";
import { streamChat } from "../services/api";
import type { ChatMessage } from "../types/chat";

export const QUESTION_POOL = [
  "What is Frans currently working on?",
  "What are Frans's technical skills?",
  "Tell me about his experience at Jet Commerce",
  "What is Frans's educational background?",
  "What did Frans build at Lazada?",
  "What leadership experience does Frans have?",
  "What AI tools has Frans worked with?",
  "What is Frans's experience with RAG systems?",
  "How does Frans approach data architecture?",
  "What is Frans's strongest technical skill?",
  "Tell me about Frans's time at Shopee",
  "What kind of roles is Frans targeting?",
  "Has Frans managed a team before?",
  "What programming languages does Frans use?",
  "What is Frans's experience with Python?",
  "Tell me about Frans's MSc at Edinburgh",
];

function pickSuggestions(lastQuestion: string): string[] {
  const pool = QUESTION_POOL.filter((q) => q !== lastQuestion);
  return [...pool].sort(() => Math.random() - 0.5).slice(0, 3);
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLimitReached, setIsLimitReached] = useState(false);
  const sessionId = useRef(crypto.randomUUID());

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming || isLimitReached) return;

      setError(null);

      const userMessage: ChatMessage = { role: "user", content };
      setMessages((prev) => [...prev, userMessage]);

      const assistantMessage: ChatMessage = { role: "assistant", content: "" };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsStreaming(true);

      await streamChat(
        {
          message: content,
          session_id: sessionId.current,
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
          const suggestions = pickSuggestions(content);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              updated[updated.length - 1] = { ...last, suggestions };
            }
            return updated;
          });
        },
        // onError
        (errorMsg) => {
          setError(errorMsg);
          setIsStreaming(false);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant" && last.content === "") {
              updated.pop();
            }
            return updated;
          });
        },
        // onLimitReached
        () => {
          setIsLimitReached(true);
          setIsStreaming(false);
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
    [isStreaming, isLimitReached]
  );

  const resetChat = useCallback(() => {
    setMessages([]);
    setError(null);
    sessionId.current = crypto.randomUUID();
  }, []);

  return { messages, isStreaming, error, isLimitReached, sendMessage, resetChat };
}
