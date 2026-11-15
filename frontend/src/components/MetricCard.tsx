import { Activity, ArrowDownRight, ArrowUpRight, Info, TrendingDown, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Metrics } from "../types";
import { formatPercentagePoints, formatPointsShort, formatRatio } from "../lib/format";

const labels: Record<keyof Metrics, { title: string; plain: string; help: string; icon: LucideIcon }> = {
  total_return: { title: "Rendement total", plain: "Gain sur la période", help: "Progression totale sur les dates étudiées, pas un rendement annuel.", icon: TrendingUp },
  annualized_volatility: { title: "Volatilité annualisée", plain: "Ampleur des fluctuations", help: "Écart-type des rendements quotidiens, ramené à une année. Une valeur plus élevée indique des mouvements plus importants; ce n’est pas une perte prévue.", icon: Activity },
  max_drawdown: { title: "Perte maximale", plain: "Plus forte baisse observée", help: "Max drawdown : baisse la plus importante depuis un sommet pendant la période. Des pertes futures pourraient être plus importantes.", icon: TrendingDown },
};

export function MetricCard({ metric, before, after }: { metric: keyof Metrics; before: number; after: number }) {
  const { title, plain, help, icon: Icon } = labels[metric];
  const worsening = metric === "annualized_volatility" ? after > before : metric === "max_drawdown" ? after < before : after < before;
  const improving = metric === "annualized_volatility" ? after < before : after > before;
  const tone = worsening ? "worse" : improving ? "better" : "neutral";
  const delta = (after - before) * 100;
  const Arrow = after >= before ? ArrowUpRight : ArrowDownRight;
  const helpId = `metric-help-${metric}`;
  return (
    <article className={`metric-card tone-${tone}`} aria-label={title}>
      <header className="metric-head">
        <span className="metric-icon" aria-hidden="true"><Icon /></span>
        <span className="metric-titles">
          <h3>{title}</h3>
          <span className="metric-plain">{plain}</span>
        </span>
        <span className="metric-info">
          <button type="button" aria-label={`Définition : ${title}`} aria-describedby={helpId}><Info aria-hidden="true" /></button>
          <span role="tooltip" id={helpId} className="metric-tooltip">{help}</span>
        </span>
      </header>
      <strong className="metric-after num"><span className="sr-only">Après : </span>{formatRatio(after)}</strong>
      <p className="metric-delta">
        <span className="delta-chip num">
          <Arrow aria-hidden="true" />
          <span aria-hidden="true">{formatPointsShort(delta)}</span>
          <span className="sr-only">Écart : {formatPercentagePoints(delta)}</span>
        </span>
        <span className="metric-before">avant <span className="num">{formatRatio(before)}</span></span>
      </p>
    </article>
  );
}
