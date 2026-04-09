import type { VoiceStatus } from "../hooks/useVoiceCall";

interface Props {
  status: VoiceStatus;
  errorMessage: string | null;
  onEnd: () => void;
  onRetry: () => void;
}

export function CallOverlay({ status, errorMessage, onEnd, onRetry }: Props) {
  const isError = !!errorMessage;

  const pulseModifier =
    status === "listening"
      ? "call-pulse--listening"
      : status === "speaking"
        ? "call-pulse--speaking"
        : "";

  return (
    <div className="call-overlay">
      <div className="call-content">
        <div className={`call-pulse ${pulseModifier}`}>
          <div className="call-pulse-ring" />
          <div className="call-pulse-ring call-pulse-ring--delay" />
          <div className="call-avatar">t</div>
        </div>

        {isError && <span className="call-error-text">{errorMessage}</span>}
      </div>

      <div className="call-bottom">
        {isError && (
          <button className="call-btn call-btn--retry" onClick={onRetry} title="Retry">
            ↻
          </button>
        )}
        <button className="call-btn call-btn--end" onClick={onEnd} title={isError ? "Close" : "End call"}>
          ✕
        </button>
      </div>
    </div>
  );
}
