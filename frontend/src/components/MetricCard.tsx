import type { Metrics } from "../types";
import { formatRatio } from "../lib/format";

const labels: Record<keyof Metrics, { title: string; help: string }> = {
  total_return: { title: "Gain sur la période", help: "Progression totale sur les dates étudiées, pas un gain annuel." },
  annualized_volatility: { title: "Fluctuations", help: "Une valeur plus élevée indique des mouvements historiques plus importants." },
  max_drawdown: { title: "Plus forte baisse", help: "Baisse la plus importante depuis un sommet pendant cette période." },
};

export function MetricCard({ metric, before, after }: { metric: keyof Metrics; before: number; after: number }) {
  const worsening = metric === "annualized_volatility" ? after > before : metric === "max_drawdown" ? after < before : false;
  return <article className="metric-card" aria-label={labels[metric].title}>
    <h3>{labels[metric].title}</h3>
    <div className="metric-values"><div><span>Avant</span><strong>{formatRatio(before)}</strong></div><div><span>Après</span><strong className={worsening ? "warning-text" : "accent-text"}>{formatRatio(after)}</strong></div></div>
    <p className="help">{labels[metric].help}</p>
  </article>;
}
