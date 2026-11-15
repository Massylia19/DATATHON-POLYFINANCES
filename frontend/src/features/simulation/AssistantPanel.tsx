import { useState } from "react";
import type { AnalysisResponse, FollowUpResponse } from "../../types";
import { api } from "../../lib/api";
import { Badge, Button, Card, Spinner } from "../../components/ui";

const suggestions = ["Pourquoi le risque change-t-il ?", "Est-ce que cela diversifie vraiment ?", "Quelles preuves pour l’ESG ?"];
export function AssistantPanel({ result, stale }: { result: AnalysisResponse | null; stale: boolean }) {
  const [question, setQuestion] = useState(""); const [answer, setAnswer] = useState<FollowUpResponse | null>(null); const [busy, setBusy] = useState(false);
  const ask = async (text = question) => { if (!result || stale || !text.trim()) return; setBusy(true); try { setAnswer(await api.followUp(result.analysis_id, text.trim())); } catch (error) { setAnswer({ status: "error", message: error instanceof Error ? error.message : "La réponse est indisponible." }); } finally { setBusy(false); } };
  return <Card className="assistant"><h2>Comprendre avec AlphaForge</h2>{result && !stale ? <><Badge>{result.analysis.persona.name} · {result.request.symbol} · {result.request.target_weight_pct} %</Badge><p>Posez une question sur ce résultat.</p><div className="suggestions">{suggestions.map(item => <button key={item} onClick={() => { setQuestion(item); void ask(item); }}>{item}<span>›</span></button>)}</div><div className="answer" aria-live="polite">{busy ? <><Spinner /> Préparation de la réponse…</> : answer?.status === "success" ? answer.answer : answer && "message" in answer ? answer.message : "Choisissez une question ou écrivez la vôtre."}</div><form onSubmit={e => { e.preventDefault(); void ask(); }}><label className="sr-only" htmlFor="question">Votre question</label><input id="question" maxLength={500} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Votre question…" /><Button className="primary" disabled={busy || !question.trim()}>Envoyer</Button></form></> : <div className="empty">{stale ? "Les paramètres ont changé. Relancez l’analyse pour poser une question sur le nouveau scénario." : "Lancez une simulation pour poser des questions sur ses résultats."}</div>}</Card>;
}
