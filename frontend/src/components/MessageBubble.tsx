import Markdown from "react-markdown";
import type { ChatMessage } from "../types/chat";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && <div className="message-avatar">AI</div>}
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
    </div>
  );
}
