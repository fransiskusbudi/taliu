import Markdown from "react-markdown";
import type { ChatMessage } from "../types/chat";

interface Props {
  message: ChatMessage;
  onSuggest?: (question: string) => void;
}

export function MessageBubble({ message, onSuggest }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && <div className="message-avatar">AI</div>}
      <div className="message-assistant-content">
        <div className={`message-bubble ${isUser ? "bubble-user" : "bubble-assistant"}`}>
          {message.content ? (
            isUser ? (
              message.content
            ) : (
              <Markdown>{message.content}</Markdown>
            )
          ) : (
            <span className="typing-cursor" />
          )}
        </div>
        {!isUser && message.suggestions && message.suggestions.length > 0 && onSuggest && (
          <div className="suggestion-chips">
            {message.suggestions.map((q) => (
              <button
                key={q}
                className="suggestion-chip"
                onClick={() => onSuggest(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
