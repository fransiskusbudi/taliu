import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  isLimitReached: boolean;
}

export function InputBar({ onSend, disabled, isLimitReached }: Props) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || disabled || isLimitReached) return;
    onSend(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="input-bar" onSubmit={handleSubmit}>
      <textarea
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
