import type { Metrics } from "../types";
import { formatPercentagePoints, formatRatio } from "../lib/format";

const labels: Record<keyof Metrics, { title: string; help: string }> = {
  total_return: { title: "Gain sur la période", help: "Progression totale sur les dates étudiées, pas un gain annuel." },
  annualized_volatility: { title: "Ampleur des fluctuations", help: "Une valeur plus élevée indique des mouvements historiques plus importants. Ce n’est pas une perte prévue." },
  max_drawdown: { title: "Plus forte baisse observée", help: "Baisse la plus importante depuis un sommet pendant cette période. Des pertes futures pourraient être plus importantes." },
};

export function MetricCard({ metric, before, after }: { metric: keyof Metrics; before: number; after: number }) {
  const worsening = metric === "annualized_volatility" ? after > before : metric === "max_drawdown" ? after < before : false;
  const delta = (after - before) * 100;
  return <article className="metric-card" aria-label={labels[metric].title}>
    <h3>{labels[metric].title}</h3>
    <div className="metric-values"><div><span>Avant</span><strong>{formatRatio(before)}</strong></div><div><span>Après</span><strong className={worsening ? "warning-text" : "accent-text"}>{formatRatio(after)}</strong></div></div>
    <p className="metric-delta">Écart : {formatPercentagePoints(delta)}</p>
    <p className="help">{labels[metric].help}</p>
  </article>;
}
