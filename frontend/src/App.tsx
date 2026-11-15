import { Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./lib/api";
import { scenarioKey } from "./lib/format";
import type { AnalysisResponse, Bootstrap, InterpretResponse, ScenarioRequest } from "./types";
import { ScenarioPanel } from "./features/simulation/ScenarioPanel";
import { ResultsWorkspace } from "./features/simulation/ResultsWorkspace";
import { AssistantPanel } from "./features/simulation/AssistantPanel";

export default function App() {
  const [data, setData] = useState<Bootstrap | null>(null); const [draft, setDraft] = useState<ScenarioRequest | null>(null); const [result, setResult] = useState<AnalysisResponse | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [proposal, setProposal] = useState<InterpretResponse | null>(null); const [theme, setTheme] = useState<"dark" | "light">("dark"); const requestNumber = useRef(0); const draftRef = useRef<ScenarioRequest | null>(null);
  useEffect(() => { const controller = new AbortController(); api.bootstrap(controller.signal).then(bootstrap => { setData(bootstrap); const first = bootstrap.scenarios[0]; setDraft({ persona_id: first.persona_id, symbol: first.symbol, target_weight_pct: first.target_weight_pct }); }).catch(reason => setError(reason instanceof Error ? reason.message : "Impossible de charger les données.")); return () => controller.abort(); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => { draftRef.current = draft; }, [draft]);
  const portfolio = useMemo(() => data && draft ? data.portfolios.find(item => item.persona_id === draft.persona_id) ?? null : null, [data, draft]);
  const stale = Boolean(result && draft && scenarioKey(result.request.persona_id, result.request.symbol, result.request.target_weight_pct) !== scenarioKey(draft.persona_id, draft.symbol, draft.target_weight_pct));
  const updateDraft = (next: ScenarioRequest) => { if (!data) return; requestNumber.current += 1; setBusy(false); const scenario = data.scenarios.find(item => item.persona_id === next.persona_id)!; const nextPortfolio = data.portfolios.find(item => item.persona_id === next.persona_id)!; const available = data.assets.filter(asset => !nextPortfolio.positions.some(position => position.symbol === asset.ticker)); setDraft({ ...next, symbol: next.persona_id !== draft?.persona_id ? (available.some(a => a.ticker === scenario.symbol) ? scenario.symbol : available[0].ticker) : next.symbol, target_weight_pct: next.persona_id !== draft?.persona_id ? scenario.target_weight_pct : next.target_weight_pct }); setProposal(null); };
  const analyze = async () => { if (!draft) return; const id = ++requestNumber.current; const submitted = { ...draft }; setBusy(true); setError(""); try { const response = await api.analyze(submitted); const current = draftRef.current; if (id === requestNumber.current && current && scenarioKey(submitted.persona_id, submitted.symbol, submitted.target_weight_pct) === scenarioKey(current.persona_id, current.symbol, current.target_weight_pct)) setResult(response); } catch (reason) { if (id === requestNumber.current) setError(reason instanceof Error ? reason.message : "L’analyse a échoué. Réessayez."); } finally { if (id === requestNumber.current) setBusy(false); } };
  const interpret = async (text: string) => { setProposal(null); try { setProposal(await api.interpret(text, draft ?? undefined)); } catch (reason) { setError(reason instanceof Error ? reason.message : "La demande n’a pas pu être comprise."); } };
  if (error && !data) return <main className="fatal"><h1>AlphaForge</h1><p>{error}</p><button onClick={() => location.reload()}>Réessayer</button></main>;
  if (!data || !draft || !portfolio) return <main className="loading" aria-live="polite">Chargement d’AlphaForge…</main>;
  return <div className="app-shell"><header><div className="brand"><span className="mark">▰</span>AlphaForge <span>Simulation fictive</span></div><button className="theme" aria-label={`Activer le thème ${theme === "dark" ? "clair" : "sombre"}`} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun /> : <Moon />}</button></header><div className="intro"><h1>Testez une idée. Comprenez ses effets.</h1><p>Comparez un portefeuille fictif avant et après un ajout.</p></div>
    {error && <div className="error global">{error} <button onClick={() => setError("")}>Fermer</button></div>}
    {proposal?.status === "ready" && <div className="proposal"><p>Paramètres compris : {proposal.request.persona_id} · {proposal.request.symbol} · {proposal.request.target_weight_pct} %</p><button onClick={() => { updateDraft(proposal.request); setProposal(null); }}>Appliquer les paramètres</button></div>}
    {proposal && proposal.status !== "ready" && <div className="notice">{"message" in proposal ? proposal.message : proposal.error.message}</div>}
    <main className="layout"><ScenarioPanel personas={data.personas} portfolio={portfolio} assets={data.assets} draft={draft} busy={busy} onDraft={updateDraft} onAnalyze={() => void analyze()} onInterpret={text => void interpret(text)} /><ResultsWorkspace result={result} stale={stale} draft={draft} assets={data.assets} /><AssistantPanel result={result} stale={stale} /></main>
    <footer>Comparaison historique pédagogique · Aucune transaction réelle</footer></div>;
}
