export function TypingIndicator() {
  return (
    <div className="message message-assistant">
      <div className="message-avatar">AI</div>
      <div className="message-bubble bubble-assistant">
        <div className="typing-indicator">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  );
}
