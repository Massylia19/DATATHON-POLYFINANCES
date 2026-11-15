import { PieChart } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type {
  AnalysisResponse,
  Asset,
  ComparisonResponse,
  EvidenceResponse,
  ProfileCheck,
  PublicEvidence,
  ScenarioRequest,
} from "../../types";
import { api } from "../../lib/api";
import { formatDate, formatRatio, formatWeight, scenarioKey } from "../../lib/format";
import { checkStatusLabels, formatMissingInformation, positionLabel } from "../../lib/presentation";
import { Badge, Button, Card, Spinner } from "../../components/ui";
import { HistoricalChart } from "../../components/HistoricalChart";
import { MetricCard } from "../../components/MetricCard";
import { ContextBar } from "../../components/AnalysisContextBar";
import { AssistantPanel } from "./AssistantPanel";

const sourceRoles: Record<string, string> = {
  src_prices_daily: "Historique quotidien des prix",
  src_fx_usdcad: "Taux de change USD/CAD",
  src_assets_universe: "Univers des placements",
  src_personas: "Profils fictifs",
  src_portfolios: "Portefeuilles fictifs de démonstration",
};

function EmptyResult({ stale }: { stale: boolean }) {
  return (
    <div className="empty main-empty">
      <h2>{stale ? "Le scénario a changé" : "Vos résultats apparaîtront ici"}</h2>
      <p>
        {stale
          ? "Relancez la simulation pour obtenir un résultat correspondant aux paramètres actuels."
          : "Choisissez un profil et un placement, puis lancez l’analyse. Aucun calcul n’est effectué automatiquement."}
      </p>
    </div>
  );
}

export function SummaryPage({
  result,
  stale,
  assets,
  onNavigate,
  onSave,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
  assets: Asset[];
  onNavigate: (page: string) => void;
  onSave: (request: ScenarioRequest) => void;
}) {
  if (!result || stale) return <Card><EmptyResult stale={stale} /></Card>;
  const { analysis } = result;
  const addedAsset = assets.find(asset => asset.ticker === result.request.symbol);
  const before = analysis.before.metrics;
  const after = analysis.after.metrics;
  return (
    <div className="results-stack">
      <Card className="result-summary">
        <div className="result-heading">
          <div>
            <p className="eyebrow">Scénario analysé</p>
            <h2>{analysis.persona.name} · {addedAsset?.name ?? result.request.symbol} ({result.request.symbol})</h2>
            <p>
              {formatWeight(result.request.target_weight_pct)} du portefeuille ·{" "}
              {formatDate(analysis.period.start)} au {formatDate(analysis.period.end)} · CAD
            </p>
          </div>
          <Button type="button" onClick={() => onSave(result.request)}>Enregistrer sur cet appareil</Button>
        </div>
        {result.status === "partial" && (
          <p className="notice" role="status">
            Calculs disponibles · explication IA indisponible. Les comparaisons
            ci-dessous proviennent du moteur de simulation.
          </p>
        )}
        {result.status === "success" && (
          <p className="success-note" role="status">Calculs et explication IA validés.</p>
        )}
        <div className="metrics">
          <MetricCard metric="total_return" before={before.total_return} after={after.total_return} />
          <MetricCard metric="annualized_volatility" before={before.annualized_volatility} after={after.annualized_volatility} />
          <MetricCard metric="max_drawdown" before={before.max_drawdown} after={after.max_drawdown} />
        </div>
        <section className="summary-card">
          <h3>Ce qu’il faut retenir</h3>
          <p>{result.presentation?.summary ?? result.explanation?.summary ?? "Les indicateurs montrent le compromis historique de cet ajout. Ils ne prédisent pas les résultats futurs."}</p>
        </section>
        <div className="chart-weights">
          <HistoricalChart analysis={analysis} />
          <section className="weights-panel" aria-labelledby="weights-title">
            <h3 id="weights-title"><PieChart aria-hidden="true" />Pondérations</h3>
            <p className="chart-note">Avant → après l’ajout</p>
            <ul className="weight-bars">
              {Object.keys({ ...analysis.before.weights_by_asset_pct, ...analysis.after.weights_by_asset_pct })
                .sort((a, b) => (analysis.after.weights_by_asset_pct[b] ?? 0) - (analysis.after.weights_by_asset_pct[a] ?? 0))
                .map(symbol => {
                  const beforeWeight = analysis.before.weights_by_asset_pct[symbol] ?? 0;
                  const afterWeight = analysis.after.weights_by_asset_pct[symbol] ?? 0;
                  const added = symbol === result.request.symbol;
                  return (
                    <li key={symbol} className={added ? "added" : undefined}>
                      <div className="weight-line">
                        <span className="weight-name" title={positionLabel(symbol, assets)}><b>{symbol}</b>{added && <em>nouveau</em>}</span>
                        <span className="weight-values">
                          {beforeWeight > 0 && <span className="weight-before">{formatWeight(beforeWeight)} → </span>}
                          <strong>{formatWeight(afterWeight)}</strong>
                        </span>
                      </div>
                      <div className="weight-track" aria-hidden="true">
                        <i className="weight-fill-before" style={{ width: `${Math.min(beforeWeight, 100)}%` }} />
                        <i className="weight-fill-after" style={{ width: `${Math.min(afterWeight, 100)}%` }} />
                      </div>
                    </li>
                  );
                })}
            </ul>
          </section>
        </div>
        <nav className="result-links" aria-label="Approfondir cette simulation">
          <button type="button" onClick={() => onNavigate("coherence")}>Examiner la cohérence du scénario <span>›</span></button>
          <button type="button" onClick={() => onNavigate("sources")}>Consulter les preuves et les sources <span>›</span></button>
          <button type="button" onClick={() => onNavigate("assistant")}>Poser une question sur ce résultat <span>›</span></button>
        </nav>
        <details className="technical-details">
          <summary>Détails techniques pour l’équipe et le jury</summary>
          <p>Les chemins de preuve, avertissements et traces d’outils ne sont affichés que dans ce mode.</p>
          <pre>{JSON.stringify({ warnings: result.warnings, explanation: result.explanation, tool_trace: result.tool_trace }, null, 2)}</pre>
        </details>
      </Card>
    </div>
  );
}

function EvidenceCards({
  analysisId,
  references,
}: {
  analysisId: string;
  references: string[];
}) {
  const [loaded, setLoaded] = useState<
    | { key: string; evidence: PublicEvidence[] }
    | { key: string; error: string }
    | null
  >(null);
  const requestId = useRef(0);
  const referencesKey = Array.from(new Set(references)).join("|");
  const key = `${analysisId}:${referencesKey}`;

  useEffect(() => {
    const id = ++requestId.current;
    const controller = new AbortController();
    if (!referencesKey) return () => controller.abort();
    api.evidence(analysisId, referencesKey.split("|"), controller.signal)
      .then((response: EvidenceResponse) => {
        if (id === requestId.current) setLoaded({ key, evidence: response.evidence });
      })
      .catch(reason => {
        if (id !== requestId.current || controller.signal.aborted) return;
        setLoaded({
          key,
          error: reason instanceof Error ? reason.message : "Les preuves ne sont pas disponibles.",
        });
      });
    return () => {
      requestId.current += 1;
      controller.abort();
    };
  }, [analysisId, key, referencesKey]);

  const active = loaded?.key === key ? loaded : null;
  const busy = Boolean(referencesKey && !active);
  if (busy) return <p className="help" aria-live="polite"><Spinner /> Chargement des preuves vérifiées…</p>;
  if (active && "error" in active) return <p className="field-error" role="status">{active.error}</p>;
  const evidence = active && "evidence" in active ? active.evidence : [];
  if (!evidence.length) return <p className="help">Aucune preuve consultable n’est associée à ce constat.</p>;
  return (
    <div className="evidence-list">
      {evidence.map((item, index) => (
        <article className="evidence-card" key={`${item.label}-${index}`}>
          <strong>{item.label}</strong>
          <p>{item.value}</p>
          {item.source && <p className="help">{item.source}{item.role ? ` — ${item.role}` : ""}{item.date ? ` · ${formatDate(item.date)}` : ""}</p>}
          {item.url && <a href={item.url} target="_blank" rel="noreferrer">Ouvrir la source originale</a>}
        </article>
      ))}
    </div>
  );
}

export function CoherencePage({
  result,
  stale,
  persona,
  onNavigate,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
  persona: string;
  onNavigate: (page: string) => void;
}) {
  if (!result || stale) return <Card><EmptyResult stale={stale} /></Card>;
  const missing = formatMissingInformation(
    result.checks.flatMap(check => check.missing_information),
  );
  return (
    <Card className="coherence-page">
      <ContextBar result={result} />
      <h2>Cohérence du scénario</h2>
      <p>
        Nous comparons les caractéristiques observées de cette simulation avec
        l’objectif déclaré du profil fictif de {persona}.
      </p>
      {result.checks.map((check: ProfileCheck) => (
        <article className={`check-card ${check.status}`} key={check.id}>
          <div className="check-card-heading">
            <h3>{check.title}</h3>
            <Badge className={`status-${check.status}`}>{checkStatusLabels[check.status]}</Badge>
          </div>
          <p>{check.message}</p>
          <details>
            <summary>Pourquoi ce constat ? Voir les éléments vérifiés</summary>
            <EvidenceCards
              key={`${result.analysis_id}:${check.evidence_refs.join("|")}`}
              analysisId={result.analysis_id}
              references={check.evidence_refs}
            />
          </details>
        </article>
      ))}
      <section className="unknowns-note">
        <h3>Ce que les données ne permettent pas de conclure</h3>
        {missing.length
          ? <ul>{missing.map(item => <li key={item}>{item}</li>)}</ul>
          : <p>Aucune information manquante supplémentaire n’a été signalée par ces contrôles.</p>}
      </section>
      <Button className="primary" type="button" onClick={() => onNavigate("simulation")}>
        Revenir à la simulation
      </Button>
    </Card>
  );
}

export function AssistantPage({
  result,
  stale,
  onApplyProposal,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
  onApplyProposal: (request: ScenarioRequest) => void;
}) {
  return (
    <AssistantPanel
      key={`${result?.analysis_id ?? "none"}:${stale}`}
      result={result}
      stale={stale}
      onApplyProposal={onApplyProposal}
    />
  );
}

export function SourcesPage({
  result,
  stale,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
}) {
  const analysis = result && !stale ? result.analysis : null;
  return (
    <Card className="sources-page">
      <h2>Sources et méthode</h2>
      <p>
        Les chiffres décrivent une simulation historique. Ils ne prédisent pas
        les résultats futurs et ne constituent pas une recommandation.
      </p>
      <h3>Comment la comparaison est faite</h3>
      <ul className="method-list">
        <li>Les deux portefeuilles sont comparés sur les mêmes dates communes.</li>
        <li>Les résultats sont exprimés en dollars canadiens.</li>
        <li>Les placements sont conservés sans rééquilibrage périodique.</li>
        <li>Les frais et les taxes ne sont pas inclus.</li>
      </ul>
      {analysis ? (
        <>
          <h3>Sources utilisées pour ce scénario</h3>
          <div className="source-list">
            {analysis.sources.map((source, index) => {
              const id = String(source.id ?? "");
              const sourceText = String(source.source ?? "Source non précisée");
              const sourceUrl = typeof source.source_url === "string" && source.source_url.startsWith("https://")
                ? source.source_url
                : null;
              const retrievedOn = typeof source.retrieved_on === "string" ? source.retrieved_on : null;
              return (
                <article className="source-card" key={id || index}>
                  <h4>{sourceText}</h4>
                  <p>{sourceRoles[id] ?? "Rôle : donnée de référence du projet"}</p>
                  {retrievedOn && <p className="help">Donnée récupérée le {formatDate(retrievedOn)}</p>}
                  {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">Consulter le document original</a>}
                </article>
              );
            })}
          </div>
          <h3>Limites de la simulation</h3>
          <ul>{analysis.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
          <details className="technical-details">
            <summary>Méthode technique</summary>
            <pre>{JSON.stringify(analysis.methodology, null, 2)}</pre>
          </details>
        </>
      ) : (
        <p className="notice" role="status">
          {stale
            ? "Le résultat précédent ne correspond plus aux paramètres actuels. Relancez l’analyse pour consulter ses sources."
            : "Les sources propres au scénario apparaîtront après le calcul."}
        </p>
      )}
    </Card>
  );
}

export function ComparisonPage({
  draft,
  personaName,
  invalid,
  assets,
}: {
  draft: ScenarioRequest;
  personaName: string;
  invalid: boolean;
  assets: Asset[];
}) {
  const [aText, setAText] = useState("5");
  const [bText, setBText] = useState("20");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastSubmittedKey, setLastSubmittedKey] = useState("");
  const [completed, setCompleted] = useState<{
    key: string;
    result: ComparisonResponse;
  } | null>(null);
  const requestId = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const currentContext = scenarioKey(
    draft.persona_id,
    draft.symbol,
    draft.target_weight_pct,
  );
  const currentContextRef = useRef(currentContext);
  const a = Number(aText.replace(",", "."));
  const b = Number(bText.replace(",", "."));
  const validWeight = (text: string, value: number) =>
    Boolean(text.trim()) && Number.isFinite(value) && value >= 1 && value <= 50
    && Math.abs((value - 1) * 2 - Math.round((value - 1) * 2)) < 1e-9;
  const valid = validWeight(aText, a) && validWeight(bText, b) && a !== b;
  const comparisonKey = `${currentContext}|${aText}|${bText}`;
  const visible = completed?.key === comparisonKey;

  useEffect(() => {
    currentContextRef.current = currentContext;
    return () => {
      requestId.current += 1;
      controllerRef.current?.abort();
      setBusy(false);
    };
  }, [currentContext]);

  const compare = async () => {
    if (!valid || invalid) return;
    const submittedKey = comparisonKey;
    const submittedContext = currentContext;
    const id = ++requestId.current;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLastSubmittedKey(submittedKey);
    setBusy(true);
    setError("");
    try {
      const response = await api.compare({
        persona_id: draft.persona_id,
        symbol: draft.symbol,
        weight_a_pct: a,
        weight_b_pct: b,
      }, controller.signal);
      if (id === requestId.current && currentContextRef.current === submittedContext) {
        setCompleted({ key: submittedKey, result: response });
      }
    } catch (reason) {
      if (id !== requestId.current || controller.signal.aborted) return;
      setError(reason instanceof Error ? reason.message : "La comparaison a échoué. Réessayez.");
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  };

  return (
    <Card className="comparison-page">
      <h2>Comparer deux variantes</h2>
      <p>
        Les deux calculs utilisent le portefeuille initial de ce profil et le
        même placement, sur exactement les mêmes dates.
      </p>
      <p className="scenario-context">{personaName} · {positionLabel(draft.symbol, assets)}</p>
      <div className="variant-form">
        <label>
          Part de la variante A (%)
          <input type="number" min="1" max="50" step="0.5" value={aText} aria-invalid={!validWeight(aText, a)} onChange={event => setAText(event.target.value)} />
        </label>
        <label>
          Part de la variante B (%)
          <input type="number" min="1" max="50" step="0.5" value={bText} aria-invalid={!validWeight(bText, b)} onChange={event => setBText(event.target.value)} />
        </label>
        <Button className="primary" disabled={busy || invalid || !valid} onClick={() => void compare()}>
          {busy ? <><Spinner />Comparaison…</> : "Comparer"}
        </Button>
      </div>
      {!valid && <p className="field-error">Choisissez deux poids distincts, de 1 % à 50 %, par pas de 0,5 %.</p>}
      {invalid && <p className="notice">Corrigez les paramètres du formulaire avant de comparer.</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      {completed && !visible && (
        <p className="notice" role="status">Les paramètres de la comparaison ont changé. Relancez la comparaison pour afficher le résultat correspondant.</p>
      )}
      {!completed && lastSubmittedKey && lastSubmittedKey !== comparisonKey && (
        <p className="notice" role="status">Les paramètres de la comparaison ont changé. Relancez la comparaison pour afficher le résultat correspondant.</p>
      )}
      {visible && completed && (
        <section className="variant-results" aria-live="polite">
          <p className="notice">
            Période commune : {formatDate(completed.result.period.start)} au {formatDate(completed.result.period.end)}.
            {completed.result.status === "partial" ? " Les explications IA des variantes ne sont pas disponibles." : ""}
          </p>
          {completed.result.variants.map((variant, index) => (
            <Card className="variant-card" key={`${variant.request.symbol}-${variant.request.target_weight_pct}`}>
              <h3>Variante {index === 0 ? "A" : "B"} · {formatWeight(variant.request.target_weight_pct)}</h3>
              <p>Gain : {formatRatio(variant.analysis.after.metrics.total_return)}</p>
              <p>Fluctuations : {formatRatio(variant.analysis.after.metrics.annualized_volatility)}</p>
              <p>Plus forte baisse : {formatRatio(variant.analysis.after.metrics.max_drawdown)}</p>
            </Card>
          ))}
          {completed.result.warnings.length > 0 && (
            <details className="technical-details">
              <summary>Détails techniques de la comparaison</summary>
              <pre>{JSON.stringify(completed.result.warnings, null, 2)}</pre>
            </details>
          )}
        </section>
      )}
    </Card>
  );
}

export function InlineEvidence({ analysisId, refs }: { analysisId: string; refs: string[] }) {
  return <EvidenceCards analysisId={analysisId} references={refs} />;
}
