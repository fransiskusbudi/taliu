import { useEffect, useMemo, useRef } from "react";
import { useChat, QUESTION_POOL } from "../hooks/useChat";
import { useTheme } from "../hooks/useTheme";
import { InputBar } from "./InputBar";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow() {
  const { messages, isStreaming, error, isLimitReached, sendMessage, resetChat } = useChat();
  const { theme, toggleTheme } = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const welcomeQuestions = useMemo(
    () => [...QUESTION_POOL].sort(() => Math.random() - 0.5).slice(0, 4),
    []
  );

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
              {welcomeQuestions.map((q) => (
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
          <MessageBubble
            key={i}
            message={msg}
            onSuggest={!isStreaming && i === messages.length - 1 ? sendMessage : undefined}
          />
        ))}

        {error && <div className="error-message">{error}</div>}

        <div ref={messagesEndRef} />
      </div>

      {isLimitReached && (
        <div className="limit-banner">
          enjoyed talking? let's connect directly →{" "}
          <a href="mailto:hi@atoue.io">hi@atoue.io</a>
          {" · "}
          <a href="https://linkedin.com/in/fransiskusbudi/" target="_blank" rel="noopener noreferrer">
            linkedin
          </a>
        </div>
      )}

      <InputBar onSend={sendMessage} disabled={isStreaming} isLimitReached={isLimitReached} />
    </div>
  );
}
