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
  // Status / who he is right now
  "What is Frans currently working on?",
  "What is Frans looking for next?",
  "Where is Frans based and is he open to relocation?",
  "What's Frans's strongest technical skill?",
  // Project deep-dives
  "What did Frans build at Brainzyme?",
  "Tell me about the AI audit layer Frans built",
  "How did Frans grow Brainzyme's Pinterest channel?",
  "What is Taliu and how was it built?",
  "Tell me about his experience at Jet Commerce",
  // Stories
  "What's a tough technical decision Frans has made?",
  "Tell me about a project that almost failed for Frans",
  "What is Frans most proud of in his career?",
  // Philosophy / how he works
  "How does Frans approach testing?",
  "How does Frans use AI in his own workflow?",
  "How does Frans balance shipping fast vs building right?",
  // Resume basics
  "What programming languages does Frans use?",
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

  const markLimitReached = useCallback(() => setIsLimitReached(true), []);

  return { messages, isStreaming, error, isLimitReached, sendMessage, resetChat, markLimitReached };
}
