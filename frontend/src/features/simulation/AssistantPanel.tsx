import { useEffect, useRef, useState } from "react";
import type {
  AnalysisResponse,
  FollowUpResponse,
  InterpretResponse,
  PublicEvidence,
  ScenarioRequest,
} from "../../types";
import { api } from "../../lib/api";
import { formatWeight } from "../../lib/format";
import { Button, Card, Spinner } from "../../components/ui";
import { ContextBar } from "../../components/AnalysisContextBar";

const suggestions = [
  "Pourquoi les fluctuations changent-elles ?",
  "Est-ce que cet ajout diversifie vraiment le portefeuille ?",
  "Quelles preuves sont disponibles pour les préférences ESG ?",
];
const FOLLOW_UP_WEIGHT = /\d+(?:[.,]\d+)?\s*(?:%|pour\s*cent|pourcent)/i;

type AnswerState =
  | {
      analysisId: string;
      question: string;
      type: "answer";
      response: FollowUpResponse;
      evidence: PublicEvidence[];
    }
  | {
      analysisId: string;
      question: string;
      type: "proposal";
      response: InterpretResponse;
      evidence: [];
    };

export function AssistantPanel({
  result,
  stale,
  onApplyProposal,
  onOpenConversation,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
  onApplyProposal: (request: ScenarioRequest) => void;
  onOpenConversation: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AnswerState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestId = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const currentAnalysisId = result?.analysis_id ?? "";

  useEffect(() => {
    return () => {
      requestId.current += 1;
      controllerRef.current?.abort();
    };
  }, [currentAnalysisId, stale]);

  const ask = async (text = question) => {
    if (!result || stale || busy || !text.trim()) return;
    const submittedQuestion = text.trim();
    const analysisId = result.analysis_id;
    const id = ++requestId.current;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setQuestion(submittedQuestion);
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      if (FOLLOW_UP_WEIGHT.test(submittedQuestion)) {
        const proposal = await api.interpret(
          submittedQuestion,
          result.request,
          controller.signal,
        );
        if (id === requestId.current && currentAnalysisId === analysisId) {
          setAnswer({
            analysisId,
            question: submittedQuestion,
            type: "proposal",
            response: proposal,
            evidence: [],
          });
        }
        return;
      }

      const response = await api.followUp(
        analysisId,
        submittedQuestion,
        controller.signal,
      );
      let evidence: PublicEvidence[] = [];
      if (response.status === "success" && response.evidence_refs.length) {
        const evidenceResponse = await api.evidence(
          analysisId,
          response.evidence_refs,
          controller.signal,
        );
        evidence = evidenceResponse.evidence;
      }
      if (id === requestId.current && currentAnalysisId === analysisId) {
        setAnswer({
          analysisId,
          question: submittedQuestion,
          type: "answer",
          response,
          evidence,
        });
      }
    } catch (reason) {
      if (id !== requestId.current || controller.signal.aborted) return;
      setError(reason instanceof Error ? reason.message : "La réponse est indisponible.");
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  };

  const activeAnswer = answer?.analysisId === currentAnalysisId ? answer : null;
  return (
    <Card className="assistant-page">
      <h2>Posez une question sur cette simulation</h2>
      <Button type="button" onClick={onOpenConversation}>Ouvrir la conversation</Button>
      {result && !stale ? (
        <>
          <ContextBar result={result} />
          <p>
            Chaque réponse s’appuie sur cette analyse et ses preuves. Les
            questions sont indépendantes; aucun historique de conversation
            n’est utilisé.
          </p>
          <div className="suggestions" aria-label="Questions suggérées">
            {suggestions.map(item => (
              <button
                type="button"
                key={item}
                disabled={busy}
                onClick={() => void ask(item)}
              >
                {item}<span aria-hidden="true">›</span>
              </button>
            ))}
          </div>
          <form onSubmit={event => { event.preventDefault(); void ask(); }}>
            <label htmlFor="assistant-question">Votre question</label>
            <input
              id="assistant-question"
              maxLength={500}
              value={question}
              onChange={event => setQuestion(event.target.value)}
              placeholder="Ex. Pourquoi ce changement mérite-t-il attention ?"
              disabled={busy}
            />
            <Button className="primary" type="submit" disabled={busy || !question.trim()}>
              {busy ? <><Spinner />Réponse en cours…</> : "Envoyer la question"}
            </Button>
          </form>
          {error && <p className="field-error" role="alert">{error}</p>}
          {busy && <p className="help" aria-live="polite">La réponse est préparée à partir des données et contrôles de cette analyse.</p>}
          {activeAnswer?.type === "answer" && (
            <section className="answer-card" aria-live="polite">
              <p className="eyebrow">Votre question</p>
              <p><b>{activeAnswer.question}</b></p>
              {activeAnswer.response.status === "success"
                ? <p>{activeAnswer.response.answer}</p>
                : <p className="notice">{activeAnswer.response.message}</p>}
              {activeAnswer.response.status === "success" && activeAnswer.evidence.length > 0 && (
                <details open>
                  <summary>Éléments qui appuient la réponse</summary>
                  <div className="evidence-list">
                    {activeAnswer.evidence.map((item, index) => (
                      <article className="evidence-card" key={`${item.label}-${index}`}>
                        <strong>{item.label}</strong>
                        <p>{item.value}</p>
                        {item.source && <p className="help">{item.source}{item.role ? ` — ${item.role}` : ""}{item.date ? ` · ${item.date}` : ""}</p>}
                        {item.url && <a href={item.url} target="_blank" rel="noreferrer">Ouvrir la source originale</a>}
                      </article>
                    ))}
                  </div>
                </details>
              )}
            </section>
          )}
          {activeAnswer?.type === "proposal" && (
            <section className="proposal-card" aria-live="polite">
              <p className="eyebrow">Variante proposée</p>
              {activeAnswer.response.status === "ready" ? (
                <>
                  <p>
                    {result.analysis.persona.name} · {activeAnswer.response.request.symbol} ·{" "}
                    {formatWeight(activeAnswer.response.request.target_weight_pct)}
                  </p>
                  <p>Cette proposition ne calcule pas encore de résultat.</p>
                  <Button className="primary" type="button" onClick={() => onApplyProposal(activeAnswer.response.status === "ready" ? activeAnswer.response.request : result.request)}>
                    Appliquer au formulaire de simulation
                  </Button>
                </>
              ) : (
                <p className="notice">
                  {activeAnswer.response.status === "error"
                    ? activeAnswer.response.error.message
                    : activeAnswer.response.message}
                </p>
              )}
            </section>
          )}
        </>
      ) : (
        <div className="empty">
          {stale
            ? "Les paramètres ont changé. Relancez l’analyse pour poser une question sur le bon scénario."
            : "Lancez une simulation pour poser une question sur ses résultats."}
        </div>
      )}
    </Card>
  );
}
