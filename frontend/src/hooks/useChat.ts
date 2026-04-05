import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHistory, streamChat } from "../services/api";
import type { ChatMessage } from "../types/chat";

const SESSION_KEY = "taliu_session_id";

function getOrCreateSessionId(): string {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const id = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, id);
  return id;
}

export const QUESTION_POOL = [
  "What is Frans currently working on?",
  "What are Frans's technical skills?",
  "Tell me about his experience at Jet Commerce",
  "What leadership experience does Frans have?",
  "What AI tools has Frans worked with?",
  "What is Frans's experience with RAG systems?",
  "How does Frans approach data architecture?",
  "Has Frans managed a team before?",
  "What programming languages does Frans use?",
  "What is Frans's experience with Python?",
  "What did Frans build at Brainzyme?",
  "What data infrastructure did Frans create at Jet Commerce?",
  "What is Frans's experience with n8n and workflow automation?",
  "What predictive modeling has Frans done?",
  "What is Frans's background in e-commerce analytics?",
  "What tools did Frans use for ETL and data pipelines?",
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
  const sessionId = useRef(getOrCreateSessionId());

  useEffect(() => {
    fetchHistory(sessionId.current).then(({ messages, limitReached }) => {
      if (messages.length > 0) {
        const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
        const lastAssistantIdx = [...messages].map((m) => m.role).lastIndexOf("assistant");
        if (lastAssistantIdx !== -1) {
          const updated = [...messages];
          updated[lastAssistantIdx] = {
            ...updated[lastAssistantIdx],
            suggestions: pickSuggestions(lastUserMsg?.content ?? ""),
          };
          setMessages(updated);
        } else {
          setMessages(messages);
        }
      }
      if (limitReached) setIsLimitReached(true);
    });
  }, []);

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
    setIsLimitReached(false);
    const newId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, newId);
    sessionId.current = newId;
  }, []);

  return { messages, isStreaming, error, isLimitReached, sendMessage, resetChat };
}
