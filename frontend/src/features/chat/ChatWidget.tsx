import { MessageCircle, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Persona } from "../../types";
import { ChatMessageView } from "./ChatMessage";
import { useChat } from "./useChat";
import "./chat.css";

const baseSuggestions = [
  "Explique-moi ce profil",
  "Comment est réparti ce portefeuille ?",
  "Que signifie la diversification ?",
];

export function ChatWidget({
  persona,
  analysisId,
  analysisLabel,
  stale,
  open,
  onOpenChange,
}: {
  persona: Persona;
  analysisId: string | null;
  analysisLabel?: string;
  stale: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { messages, pending, send } = useChat(persona, analysisId);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const shouldFollow = useRef(true);
  const suggestions = analysisId ? [...baseSuggestions, "Explique-moi les résultats"] : baseSuggestions;

  useEffect(() => {
    if (open) window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (!open || !shouldFollow.current) return;
    messagesRef.current?.scrollTo?.({ top: messagesRef.current.scrollHeight });
  }, [messages, open, pending]);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onOpenChange(false);
        window.setTimeout(() => launcherRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onOpenChange, open]);

  const submit = () => {
    const question = draft.trim();
    if (!question || question.length > 2000 || pending) return;
    setDraft("");
    shouldFollow.current = true;
    void send(question);
  };

  return (
    <>
      {open && (
        <section className="chat-window" role="dialog" aria-label="Assistant AlphaForge">
          <header className="chat-header">
            <span className="chat-avatar" aria-hidden="true"><Sparkles /></span>
            <div><strong>Assistant AlphaForge</strong><span>Comprendre votre simulation</span></div>
            <button type="button" aria-label="Fermer la conversation" onClick={() => { onOpenChange(false); window.setTimeout(() => launcherRef.current?.focus(), 0); }}><X /></button>
          </header>
          <div className="chat-context">
            <span>Profil fictif : {persona.name}</span>
            {analysisId && analysisLabel && <span>Simulation active : {analysisLabel}</span>}
            {stale && <span className="chat-stale">Paramètres modifiés : relancez la simulation pour discuter de ses résultats.</span>}
          </div>
          <div
            className="chat-messages"
            ref={messagesRef}
            onScroll={event => {
              const node = event.currentTarget;
              shouldFollow.current = node.scrollHeight - node.scrollTop - node.clientHeight < 48;
            }}
          >
            <p className="chat-message chat-message--assistant">
              Bonjour 😊 Je suis l’assistant AlphaForge. Je peux vous aider à comprendre le profil de {persona.name}, son portefeuille et vos simulations.
            </p>
            {messages.length === 0 && (
              <div className="chat-suggestions" aria-label="Questions suggérées">
                {suggestions.map(suggestion => <button type="button" key={suggestion} onClick={() => void send(suggestion)}>{suggestion}</button>)}
              </div>
            )}
            {messages.map(message => <ChatMessageView key={message.id} message={message} onRetry={item => void send(item.content, item.id)} />)}
            {pending && <div className="chat-typing" role="status" aria-label="L’assistant rédige sa réponse"><i /><i /><i /><span>Réponse en cours…</span></div>}
          </div>
          <div className="chat-composer">
            <textarea
              ref={inputRef}
              rows={1}
              maxLength={2000}
              value={draft}
              disabled={pending}
              aria-label="Votre message"
              placeholder="Posez votre question…"
              onChange={event => setDraft(event.target.value)}
              onKeyDown={event => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
            />
            <button type="button" aria-label="Envoyer" disabled={pending || !draft.trim()} onClick={submit}><Send /></button>
          </div>
        </section>
      )}
      <button
        ref={launcherRef}
        className="chat-launcher"
        type="button"
        aria-label={open ? "Fermer l’assistant" : "Ouvrir l’assistant"}
        aria-expanded={open}
        onClick={() => onOpenChange(!open)}
      >
        {open ? <X /> : <MessageCircle />}
      </button>
    </>
  );
}
