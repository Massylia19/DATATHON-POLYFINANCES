import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";
import type { AnalysisResponse, Asset, ComparisonResponse, ScenarioRequest } from "../../types";
import { api } from "../../lib/api";
import { formatDate, formatWeight } from "../../lib/format";
import { Card, Button, Spinner, Badge } from "../../components/ui";
import { HistoricalChart } from "../../components/HistoricalChart";
import { MetricCard } from "../../components/MetricCard";

const statusLabels = { consistent: "Cohérent sur ce point", tension: "Point de vigilance", insufficient_information: "Informations insuffisantes" } as const;
const missingLabels: Record<string, string> = { loss_absorption_capacity: "La perte que cette personne pourrait supporter", liquidity_needs: "Ses besoins d’argent à court terme", planned_withdrawals: "Ses retraits prévus", etf_holdings: "La composition détaillée des fonds", asset_specific_esg_evidence: "Des informations ESG propres à cet actif", independent_esg_assessment: "Une évaluation ESG indépendante" };

export function ResultsWorkspace({ result, stale, draft, assets }: { result: AnalysisResponse | null; stale: boolean; draft: ScenarioRequest; assets: Asset[] }) {
  return <Card className="workspace"><Tabs.Root defaultValue="summary"><Tabs.List className="tabs" aria-label="Sections des résultats"><Tabs.Trigger value="summary">Synthèse</Tabs.Trigger><Tabs.Trigger value="variants">Variantes</Tabs.Trigger><Tabs.Trigger value="sources">Sources et méthode</Tabs.Trigger></Tabs.List>
    <Tabs.Content value="summary"><Summary result={result} stale={stale} assets={assets} /></Tabs.Content>
    <Tabs.Content value="variants"><Variants draft={draft} /></Tabs.Content>
    <Tabs.Content value="sources"><Sources result={result} stale={stale} /></Tabs.Content>
  </Tabs.Root></Card>;
}

function Summary({ result, stale, assets }: { result: AnalysisResponse | null; stale: boolean; assets: Asset[] }) {
  if (!result) return <div className="empty main-empty"><h2>Vos résultats apparaîtront ici</h2><p>Choisissez un profil et un actif, puis lancez l’analyse.</p></div>;
  if (stale) return <div className="empty main-empty"><h2>Les paramètres ont changé</h2><p>Relancez l’analyse pour afficher les résultats de ce scénario.</p></div>;
  const { analysis } = result; const asset = assets.find(a => a.ticker === result.request.symbol);
  return <div className="summary"><div className="result-heading"><div><Badge>{analysis.persona.name} · {asset?.name ?? result.request.symbol} · {formatWeight(result.request.target_weight_pct)}</Badge></div><span>{formatDate(analysis.period.start)} – {formatDate(analysis.period.end)} · {analysis.currency}</span></div>
    {result.status === "partial" && <div className="notice">Calculs disponibles · explication IA indisponible</div>}
    <div className="metrics"><MetricCard metric="total_return" before={analysis.before.metrics.total_return} after={analysis.after.metrics.total_return} /><MetricCard metric="annualized_volatility" before={analysis.before.metrics.annualized_volatility} after={analysis.after.metrics.annualized_volatility} /><MetricCard metric="max_drawdown" before={analysis.before.metrics.max_drawdown} after={analysis.after.metrics.max_drawdown} /></div>
    <section className="summary-card"><h3>Ce qu’il faut retenir</h3><p>{result.presentation?.summary ?? result.explanation?.summary ?? "La comparaison historique est disponible ci-dessous."}</p></section>
    <HistoricalChart analysis={analysis} />
    <section className="checks"><h3>Cohérence avec le profil</h3>{result.checks.map(check => <article key={check.id} className={`check ${check.status}`}><div><strong>{check.title}</strong><p>{check.message}</p></div><span>{statusLabels[check.status]}</span></article>)}</section>
    {Array.from(new Set(result.checks.flatMap(c => c.missing_information))).length > 0 && <section><h3>Informations qui manquent</h3><ul>{Array.from(new Set(result.checks.flatMap(c => c.missing_information))).map(item => <li key={item}>{missingLabels[item] ?? "Une information complémentaire à vérifier"}</li>)}</ul></section>}
    <details><summary>Pondérations détaillées</summary><div className="table-scroll"><table><thead><tr><th>Placement</th><th>Avant</th><th>Après</th></tr></thead><tbody>{Object.keys({ ...analysis.before.weights_by_asset_pct, ...analysis.after.weights_by_asset_pct }).sort().map(symbol => <tr key={symbol}><td>{symbol}</td><td>{formatWeight(analysis.before.weights_by_asset_pct[symbol] ?? 0)}</td><td>{formatWeight(analysis.after.weights_by_asset_pct[symbol] ?? 0)}</td></tr>)}</tbody></table></div></details>
    <details><summary>Détails techniques</summary><pre>{JSON.stringify({ warnings: result.warnings, tool_trace: result.tool_trace }, null, 2)}</pre></details>
  </div>;
}

function Variants({ draft }: { draft: ScenarioRequest }) { const [a, setA] = useState(5); const [b, setB] = useState(20); const [busy, setBusy] = useState(false); const [result, setResult] = useState<ComparisonResponse | null>(null); const [error, setError] = useState("");
  const compare = async () => { if (a === b) { setError("Les deux poids doivent être différents."); return; } setBusy(true); setError(""); setResult(null); try { setResult(await api.compare({ persona_id: draft.persona_id, symbol: draft.symbol, weight_a_pct: a, weight_b_pct: b })); } catch (reason) { setError(reason instanceof Error ? reason.message : "La comparaison a échoué."); } finally { setBusy(false); } };
  return <section className="variants"><h2>Comparer deux variantes</h2><p>Les deux simulations utilisent le même profil, le même actif et une période commune.</p><div className="variant-form"><label>Poids A (%)<input type="number" min="1" max="50" step="0.5" value={a} onChange={e => setA(Number(e.target.value))} /></label><label>Poids B (%)<input type="number" min="1" max="50" step="0.5" value={b} onChange={e => setB(Number(e.target.value))} /></label><Button className="primary" disabled={busy} onClick={() => void compare()}>{busy ? <><Spinner />Comparaison…</> : "Comparer"}</Button></div>{error && <div className="error">{error}</div>}{result && <div className="variant-results">{result.variants.map((variant, index) => <Card key={index}><h3>Variante {index ? "B" : "A"} · {variant.request.target_weight_pct} %</h3><p>Gain : {(variant.analysis.after.metrics.total_return * 100).toLocaleString("fr-CA", { maximumFractionDigits: 2 })} %</p><p>Fluctuations : {(variant.analysis.after.metrics.annualized_volatility * 100).toLocaleString("fr-CA", { maximumFractionDigits: 2 })} %</p></Card>)}</div>}</section>;
}

function Sources({ result, stale }: { result: AnalysisResponse | null; stale: boolean }) { if (!result || stale) return <div className="empty main-empty">Lancez l’analyse du scénario courant pour consulter ses sources.</div>; const analysis = result.analysis; return <section className="sources"><h2>Sources et méthode</h2><p>Les deux portefeuilles sont comparés sur les mêmes dates, en dollars canadiens. Les positions sont conservées sans rééquilibrage; les frais et taxes sont exclus.</p><h3>Sources</h3>{analysis.sources.map((source, index) => <article key={String(source.id ?? index)}><strong>{String(source.provider ?? source.origin ?? source.id ?? "Source")}</strong><p>{String(source.description ?? source.role ?? "Données utilisées par le moteur.")}</p>{source.url ? <a href={String(source.url)} target="_blank" rel="noreferrer">Consulter la source</a> : null}</article>)}<h3>Limites</h3><ul>{analysis.limitations.map(item => <li key={item}>{item}</li>)}</ul><details><summary>Méthode complète</summary><pre>{JSON.stringify(analysis.methodology, null, 2)}</pre></details></section>; }
