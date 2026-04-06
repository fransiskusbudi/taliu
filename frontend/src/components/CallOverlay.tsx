import { useEffect } from "react";
import type { VoiceStatus } from "../hooks/useVoiceCall";

interface Props {
  status: VoiceStatus;
  errorMessage: string | null;
  onEnd: () => void;
  onRetry: () => void;
}

const STATUS_LABELS: Record<VoiceStatus, string> = {
  idle: "Starting...",
  listening: "Listening...",
  processing: "Processing...",
  speaking: "Speaking...",
  error: "Call ended",
};

export function CallOverlay({ status, errorMessage, onEnd, onRetry }: Props) {
  // Prevent background scroll while overlay is open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const isError = !!errorMessage;

  return (
    <div className="call-overlay">
      <div className="call-content">
        <div className={`call-pulse ${status === "speaking" ? "call-pulse--speaking" : ""} ${status === "listening" ? "call-pulse--listening" : ""}`}>
          <div className="call-pulse-ring" />
          <div className="call-pulse-ring call-pulse-ring--delay" />
          <div className="call-avatar">T</div>
        </div>

        <p className="call-status-text">
          {isError ? errorMessage : STATUS_LABELS[status]}
        </p>

        <div className="call-actions">
          {isError ? (
            <>
              <button className="call-btn call-btn--retry" onClick={onRetry}>
                try again
              </button>
              <button className="call-btn call-btn--end" onClick={onEnd}>
                close
              </button>
            </>
          ) : (
            <button className="call-btn call-btn--end" onClick={onEnd}>
              end call
            </button>
          )}
        </div>
      </div>
    </div>
  );
}