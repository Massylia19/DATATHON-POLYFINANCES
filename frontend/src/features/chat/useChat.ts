import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../lib/api";
import type { ChatMessage, Persona } from "../../types";

export interface DisplayMessage extends ChatMessage {
  id: string;
  error?: string;
}

interface Conversation {
  messages: DisplayMessage[];
  pending: boolean;
}

const emptyConversation = (): Conversation => ({ messages: [], pending: false });

export function useChat(persona: Persona, analysisId: string | null) {
  const contextKey = `${persona.id}:${analysisId ?? "profile"}`;
  const [conversations, setConversations] = useState<Record<string, Conversation>>({});
  const conversationsRef = useRef(conversations);
  const pendingKeys = useRef(new Set<string>());
  useEffect(() => {
    conversationsRef.current = conversations;
  }, [conversations]);
  const conversation = conversations[contextKey] ?? emptyConversation();

  const send = useCallback(async (rawQuestion: string, retryMessageId?: string) => {
    const question = rawQuestion.trim();
    const keyAtSend = contextKey;
    const current = conversationsRef.current[keyAtSend] ?? emptyConversation();
    if (!question || question.length > 2000 || pendingKeys.current.has(keyAtSend)) return;
    pendingKeys.current.add(keyAtSend);
    const history = current.messages
      .filter(message => !message.error && message.id !== retryMessageId)
      .map(({ role, content }) => ({ role, content }))
      .slice(-10);
    const userId = retryMessageId ?? crypto.randomUUID();
    const nextMessages = retryMessageId
      ? current.messages.map(message => message.id === retryMessageId ? { ...message, error: undefined } : message)
      : [...current.messages, { id: userId, role: "user" as const, content: question }];
    setConversations(all => ({ ...all, [keyAtSend]: { messages: nextMessages, pending: true } }));
    try {
      const response = await api.chat({
        persona_id: persona.id,
        question,
        analysis_id: analysisId,
        history,
      });
      setConversations(all => {
        const target = all[keyAtSend] ?? { messages: nextMessages, pending: true };
        return {
          ...all,
          [keyAtSend]: {
            pending: false,
            messages: [...target.messages, { id: crypto.randomUUID(), role: "assistant", content: response.answer }],
          },
        };
      });
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "La réponse est indisponible.";
      setConversations(all => {
        const target = all[keyAtSend] ?? { messages: nextMessages, pending: true };
        return {
          ...all,
          [keyAtSend]: {
            pending: false,
            messages: target.messages.map(item => item.id === userId ? { ...item, error: message } : item),
          },
        };
      });
    } finally {
      pendingKeys.current.delete(keyAtSend);
    }
  }, [analysisId, contextKey, persona.id]);

  return useMemo(() => ({
    contextKey,
    messages: conversation.messages,
    pending: conversation.pending,
    send,
  }), [contextKey, conversation.messages, conversation.pending, send]);
}
