import { useEffect, useMemo, useRef, useState } from "react";
import { useChat, QUESTION_POOL } from "../hooks/useChat";
import { useTheme } from "../hooks/useTheme";
import { useVoiceCall } from "../hooks/useVoiceCall";
import { InputBar } from "./InputBar";
import { MessageBubble } from "./MessageBubble";
import { CallOverlay } from "./CallOverlay";

const SESSION_KEY = "taliu_session_id";

function getSessionId(): string {
  return localStorage.getItem(SESSION_KEY) ?? "";
}

export function ChatWindow() {
  const { messages, isStreaming, error, isLimitReached, sendMessage, resetChat } = useChat();
  const { theme, toggleTheme } = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isCallOpen, setIsCallOpen] = useState(false);

  const { status: callStatus, errorMessage: callError, startCall, endCall } = useVoiceCall(() => {
    // voice turn hit the message limit
    setIsCallOpen(false);
  });

  const welcomeQuestions = useMemo(
    () => [...QUESTION_POOL].sort(() => Math.random() - 0.5).slice(0, 4),
    []
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleStartCall = async () => {
    setIsCallOpen(true);
    await startCall(getSessionId());
  };

  const handleEndCall = () => {
    endCall();
    setIsCallOpen(false);
  };

  const handleRetryCall = async () => {
    endCall();
    await startCall(getSessionId());
  };

  return (
    <div className="chat-container">
      {isCallOpen && (
        <CallOverlay
          status={callStatus}
          errorMessage={callError}
          onEnd={handleEndCall}
          onRetry={handleRetryCall}
        />
      )}

      <header className="chat-header">
        <div className="chat-header-left">
          <h1>taliu</h1>
          <p>get to know Frans — ask me anything</p>
        </div>
        <div className="chat-header-actions">
          <button
            className="call-header-btn"
            onClick={handleStartCall}
            disabled={isLimitReached}
            title="Start a voice call with Taliu"
          >
            <span className="call-header-btn-icon">✆</span>
            <span className="call-header-btn-label">Call Taliu</span>
          </button>
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

            {!isLimitReached && (
              <button className="call-welcome-card" onClick={handleStartCall}>
                <span className="call-welcome-icon">✆</span>
                <span className="call-welcome-text">
                  <span className="call-welcome-title">Call Taliu</span>
                  <span className="call-welcome-subtitle">Talk to me directly</span>
                </span>
              </button>
            )}

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
