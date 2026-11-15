import type { DisplayMessage } from "./useChat";

export function ChatMessageView({ message, onRetry }: { message: DisplayMessage; onRetry: (message: DisplayMessage) => void }) {
  return (
    <div className={`chat-message-row chat-message-row--${message.role}`}>
      <p className={`chat-message chat-message--${message.role}`}>{message.content}</p>
      {message.error && (
        <div className="chat-message-error" role="alert">
          <span>{message.error}</span>
          <button type="button" onClick={() => onRetry(message)}>Réessayer</button>
        </div>
      )}
    </div>
  );
}
