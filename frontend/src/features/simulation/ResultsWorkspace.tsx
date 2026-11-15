import * as Tabs from "@radix-ui/react-tabs";
import { BarChart3, Bookmark, Lightbulb, RefreshCw } from "lucide-react";
import { AlertTriangle, ArrowLeft, BookOpen, CheckCircle2, ChevronDown, Code2, Database, ExternalLink, GitCompare, HelpCircle, LineChart, ListChecks, PieChart, ShieldCheck, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
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
import { Badge, Button, Card, InfoTip, Spinner } from "../../components/ui";
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

const statusIcons: Record<ProfileCheck["status"], LucideIcon> = {
  consistent: CheckCircle2,
  tension: AlertTriangle,
  insufficient_information: HelpCircle,
};

function EmptyResult({ stale }: { stale: boolean }) {
  const Icon = stale ? RefreshCw : BarChart3;
  return (
    <div className="empty main-empty">
      <Icon aria-hidden="true" className="empty-icon" />
      <h2>{stale ? "Le scénario a changé" : "Vos résultats apparaîtront ici"}</h2>
      <p>
        {stale
          ? "Relancez l’analyse pour mettre les résultats à jour."
          : "Cliquez sur « Analyser le scénario » pour lancer le calcul."}
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
  comparison,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
  assets: Asset[];
  onNavigate: (page: string) => void;
  onSave: (request: ScenarioRequest) => void;
  comparison?: ReactNode;
}) {
  if (!result || stale) return <><Card><EmptyResult stale={stale} /></Card>{comparison}</>;
  const { analysis } = result;
  const addedAsset = assets.find(asset => asset.ticker === result.request.symbol);
  const before = analysis.before.metrics;
  const after = analysis.after.metrics;
  return (
    <div className="results-stack">
      <Card className="result-summary">
        <div className="result-heading">
          <div>
            <h2>{analysis.persona.name} · {addedAsset?.name ?? result.request.symbol} ({result.request.symbol})</h2>
            <p>
              {formatWeight(result.request.target_weight_pct)} du portefeuille ·{" "}
              {formatDate(analysis.period.start)} au {formatDate(analysis.period.end)} · CAD
            </p>
          </div>
          <div className="result-actions">
            {result.status === "partial" && (
              <span className="ai-badge ai-off" role="status">
                <AlertTriangle aria-hidden="true" />IA indisponible
                <InfoTip label="Pourquoi l’IA est indisponible">
                  Calculs disponibles · explication IA indisponible. Les comparaisons proviennent du moteur de simulation.
                </InfoTip>
              </span>
            )}
            {result.status === "success" && (
              <span className="ai-badge ai-on" role="status"><Sparkles aria-hidden="true" />Explication IA validée</span>
            )}
            <Button type="button" aria-label="Enregistrer sur cet appareil" onClick={() => onSave(result.request)}>
              <Bookmark aria-hidden="true" /><span aria-hidden="true">Enregistrer</span>
            </Button>
          </div>
        </div>
        <div className="metrics">
          <MetricCard metric="total_return" before={before.total_return} after={after.total_return} />
          <MetricCard metric="annualized_volatility" before={before.annualized_volatility} after={after.annualized_volatility} />
          <MetricCard metric="max_drawdown" before={before.max_drawdown} after={after.max_drawdown} />
        </div>
        <section className="summary-card">
          <h3><Lightbulb aria-hidden="true" />Ce qu’il faut retenir</h3>
          <p>{result.presentation?.summary ?? result.explanation?.summary ?? "Les indicateurs montrent le compromis historique de cet ajout. Ils ne prédisent pas les résultats futurs."}</p>
        </section>
        <Tabs.Root defaultValue="chart" className="result-tabs">
          <Tabs.List className="tab-list" aria-label="Détails du résultat">
            <Tabs.Trigger value="chart"><LineChart aria-hidden="true" />Graphique et pondérations</Tabs.Trigger>
            <Tabs.Trigger value="variants"><GitCompare aria-hidden="true" />Comparer deux variantes</Tabs.Trigger>
            <Tabs.Trigger value="technical"><Code2 aria-hidden="true" />Détails techniques</Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="chart" forceMount className="tab-panel">
        <div className="chart-weights">
          <HistoricalChart analysis={analysis} />
          <section className="weights-panel" aria-labelledby="weights-title">
            <h3 id="weights-title"><PieChart aria-hidden="true" />Pondérations</h3>
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
          </Tabs.Content>
          <Tabs.Content value="variants" forceMount className="tab-panel">
            {comparison}
          </Tabs.Content>
          <Tabs.Content value="technical" className="tab-panel technical-panel">
            <p className="help">Chemins de preuve, avertissements et traces d’outils, pour l’équipe et le jury.</p>
            <pre>{JSON.stringify({ warnings: result.warnings, explanation: result.explanation, tool_trace: result.tool_trace }, null, 2)}</pre>
          </Tabs.Content>
        </Tabs.Root>
        <nav className="result-links" aria-label="Approfondir cette simulation">
          <button type="button" onClick={() => onNavigate("coherence")}><ShieldCheck aria-hidden="true" />Examiner la cohérence du scénario <span>›</span></button>
          <button type="button" onClick={() => onNavigate("sources")}><BookOpen aria-hidden="true" />Consulter les preuves et les sources <span>›</span></button>
          <button type="button" onClick={() => onNavigate("assistant")}><Sparkles aria-hidden="true" />Poser une question sur ce résultat <span>›</span></button>
        </nav>
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
  onNavigate,
}: {
  result: AnalysisResponse | null;
  stale: boolean;
  persona?: string;
  onNavigate: (page: string) => void;
}) {
  if (!result || stale) return <Card><EmptyResult stale={stale} /></Card>;
  const missing = formatMissingInformation(
    result.checks.flatMap(check => check.missing_information),
  );
  const counts = {
    consistent: result.checks.filter(check => check.status === "consistent").length,
    tension: result.checks.filter(check => check.status === "tension").length,
    insufficient_information: result.checks.filter(check => check.status === "insufficient_information").length,
  };
  return (
    <Card className="coherence-page">
      <div className="coherence-top">
        <ContextBar result={result} />
        <ul className="status-counts" aria-label="Résumé des contrôles">
          <li className="count-consistent"><CheckCircle2 aria-hidden="true" />{counts.consistent} cohérent{counts.consistent > 1 ? "s" : ""}</li>
          <li className="count-tension"><AlertTriangle aria-hidden="true" />{counts.tension} vigilance</li>
          <li className="count-insufficient"><HelpCircle aria-hidden="true" />{counts.insufficient_information} insuffisant{counts.insufficient_information > 1 ? "s" : ""}</li>
        </ul>
      </div>
      <div className="check-list">
        {result.checks.map((check: ProfileCheck) => {
          const StatusIcon = statusIcons[check.status];
          return (
            <details className={`check-card ${check.status}`} key={check.id}>
              <summary className="check-card-heading">
                <span className={`check-icon icon-${check.status}`} aria-hidden="true"><StatusIcon /></span>
                <h3>{check.title}</h3>
                <Badge className={`status-${check.status}`}>{checkStatusLabels[check.status]}</Badge>
                <ChevronDown aria-hidden="true" className="check-chevron" />
              </summary>
              <div className="check-body">
                <p>{check.message}</p>
                <details className="evidence-toggle">
                  <summary>Pourquoi ce constat ? Voir les éléments vérifiés</summary>
                  <EvidenceCards
                    key={`${result.analysis_id}:${check.evidence_refs.join("|")}`}
                    analysisId={result.analysis_id}
                    references={check.evidence_refs}
                  />
                </details>
              </div>
            </details>
          );
        })}
      </div>
      <section className="unknowns-note">
        <h3><AlertTriangle aria-hidden="true" className="inline-icon" />Ce que les données ne permettent pas de conclure</h3>
        {missing.length
          ? <ul>{missing.map(item => <li key={item}>{item}</li>)}</ul>
          : <p>Aucune information manquante supplémentaire n’a été signalée par ces contrôles.</p>}
      </section>
      <Button className="primary" type="button" onClick={() => onNavigate("simulation")}>
        <ArrowLeft aria-hidden="true" />Revenir à la simulation
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
  const pending = stale
    ? "Le résultat précédent ne correspond plus aux paramètres actuels. Relancez l’analyse pour consulter ses sources."
    : "Disponible après le calcul d’un scénario.";
  return (
    <Card className="sources-page">
      <div className="accordion-list">
        <details className="accordion-item">
          <summary>
            <span className="accordion-icon" aria-hidden="true"><ListChecks /></span>
            <span className="accordion-title"><strong>Méthode de calcul</strong><span>Comment les deux portefeuilles sont comparés</span></span>
            <span className="accordion-count">4</span>
            <ChevronDown aria-hidden="true" className="check-chevron" />
          </summary>
          <div className="accordion-body">
            <ul className="method-list">
              <li>Les deux portefeuilles sont comparés sur les mêmes dates communes.</li>
              <li>Les résultats sont exprimés en dollars canadiens.</li>
              <li>Les placements sont conservés sans rééquilibrage périodique.</li>
              <li>Les frais et les taxes ne sont pas inclus.</li>
            </ul>
            {analysis && (
              <details className="technical-details">
                <summary>Méthode technique</summary>
                <pre>{JSON.stringify(analysis.methodology, null, 2)}</pre>
              </details>
            )}
          </div>
        </details>

        <details className="accordion-item">
          <summary>
            <span className="accordion-icon" aria-hidden="true"><Database /></span>
            <span className="accordion-title"><strong>Sources des données</strong><span>D’où viennent les prix, les taux et les profils</span></span>
            {analysis && <span className="accordion-count">{analysis.sources.length}</span>}
            <ChevronDown aria-hidden="true" className="check-chevron" />
          </summary>
          <div className="accordion-body">
            {analysis ? (
              <ul className="source-rows">
                {analysis.sources.map((source, index) => {
                  const id = String(source.id ?? "");
                  const sourceText = String(source.source ?? "Source non précisée");
                  const sourceUrl = typeof source.source_url === "string" && source.source_url.startsWith("https://")
                    ? source.source_url
                    : null;
                  const retrievedOn = typeof source.retrieved_on === "string" ? source.retrieved_on : null;
                  return (
                    <li key={id || index}>
                      <span className="source-main">
                        <strong>{sourceRoles[id] ?? "Donnée de référence du projet"}</strong>
                        <span>{sourceText}{retrievedOn ? ` · récupérée le ${formatDate(retrievedOn)}` : ""}</span>
                      </span>
                      {sourceUrl && (
                        <a href={sourceUrl} target="_blank" rel="noreferrer" aria-label={`Consulter le document original : ${sourceText}`}>
                          <ExternalLink aria-hidden="true" />Original
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : <p className="help" role="status">{pending}</p>}
          </div>
        </details>

        <details className="accordion-item">
          <summary>
            <span className="accordion-icon" aria-hidden="true"><AlertTriangle /></span>
            <span className="accordion-title"><strong>Limites de la simulation</strong><span>Ce que les chiffres ne prennent pas en compte</span></span>
            {analysis && <span className="accordion-count">{analysis.limitations.length}</span>}
            <ChevronDown aria-hidden="true" className="check-chevron" />
          </summary>
          <div className="accordion-body">
            {analysis
              ? <ul className="limit-list">{analysis.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
              : <p className="help" role="status">{pending}</p>}
          </div>
        </details>
      </div>
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
          {busy ? <><Spinner />Comparaison…</> : <><GitCompare aria-hidden="true" />Comparer</>}
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
