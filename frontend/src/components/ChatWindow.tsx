import { useEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";
import { useTheme } from "../hooks/useTheme";
import { InputBar } from "./InputBar";
import { MessageBubble } from "./MessageBubble";

const SUGGESTED_QUESTIONS = [
  "What is Frans currently working on?",
  "What are Frans's technical skills?",
  "Tell me about his experience at Jet Commerce",
  "What is Frans's educational background?",
];

export function ChatWindow() {
  const { messages, isStreaming, error, sendMessage, resetChat } = useChat();
  const { theme, toggleTheme } = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-container">
      <header className="chat-header">
        <div className="chat-header-left">
          <h1>taliu</h1>
          <p>get to know Frans — ask me anything</p>
        </div>
        <div className="chat-header-actions">
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          {messages.length > 0 && (
            <button className="reset-button" onClick={resetChat}>
              new chat
            </button>
          )}
        </div>
      </header>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-section">
            <div className="welcome-text">
              <h2>hi, i'm taliu — Frans's ai agent</h2>
              <p>
                ask me anything about Frans — his work, skills, background, and more. try one of these:
              </p>
            </div>
            <div className="suggested-questions">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="suggestion-chip"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {error && <div className="error-message">{error}</div>}

        <div ref={messagesEndRef} />
      </div>

      <InputBar onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
