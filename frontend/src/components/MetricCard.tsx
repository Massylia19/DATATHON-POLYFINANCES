import { Activity, ArrowDownRight, ArrowUpRight, Info, TrendingDown, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Metrics } from "../types";
import { formatPercentagePoints, formatRatio } from "../lib/format";

const labels: Record<keyof Metrics, { title: string; help: string; icon: LucideIcon }> = {
  total_return: { title: "Gain sur la période", help: "Progression totale sur les dates étudiées, pas un gain annuel.", icon: TrendingUp },
  annualized_volatility: { title: "Ampleur des fluctuations", help: "Une valeur plus élevée indique des mouvements historiques plus importants. Ce n’est pas une perte prévue.", icon: Activity },
  max_drawdown: { title: "Plus forte baisse observée", help: "Baisse la plus importante depuis un sommet pendant cette période. Des pertes futures pourraient être plus importantes.", icon: TrendingDown },
};

const shortPoints = new Intl.NumberFormat("fr-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "always" });

export function MetricCard({ metric, before, after }: { metric: keyof Metrics; before: number; after: number }) {
  const { title, help, icon: Icon } = labels[metric];
  const worsening = metric === "annualized_volatility" ? after > before : metric === "max_drawdown" ? after < before : false;
  const improving = metric === "total_return" ? after > before : metric === "annualized_volatility" ? after < before : after > before;
  const tone = worsening ? "worse" : improving ? "better" : "neutral";
  const delta = (after - before) * 100;
  const Arrow = after >= before ? ArrowUpRight : ArrowDownRight;
  const helpId = `metric-help-${metric}`;
  return (
    <article className={`metric-card tone-${tone}`} aria-label={title}>
      <header className="metric-head">
        <span className="metric-icon" aria-hidden="true"><Icon /></span>
        <h3>{title}</h3>
        <span className="metric-info">
          <button type="button" aria-label={`Définition : ${title}`} aria-describedby={helpId}><Info aria-hidden="true" /></button>
          <span role="tooltip" id={helpId} className="metric-tooltip">{help}</span>
        </span>
      </header>
      <strong className="metric-after"><span className="sr-only">Après : </span>{formatRatio(after)}</strong>
      <p className="metric-delta">
        <span className="delta-chip">
          <Arrow aria-hidden="true" />
          <span aria-hidden="true">{shortPoints.format(delta)} pts</span>
          <span className="sr-only">Écart : {formatPercentagePoints(delta)}</span>
        </span>
        <span className="metric-before">avant {formatRatio(before)}</span>
      </p>
    </article>
  );
}
