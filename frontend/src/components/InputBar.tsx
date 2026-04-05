import { useEffect, useRef, useState } from "react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  isLimitReached: boolean;
}

export function InputBar({ onSend, disabled, isLimitReached }: Props) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const submit = () => {
    if (!input.trim() || disabled || isLimitReached) return;
    onSend(input.trim());
    setInput("");
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form className="input-bar" onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about Frans's experience..."
        disabled={disabled || isLimitReached}
        rows={1}
      />
      <button type="submit" disabled={disabled || isLimitReached || !input.trim()}>
        Send
      </button>
    </form>
  );
}
