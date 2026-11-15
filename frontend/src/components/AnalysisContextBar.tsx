import type { AnalysisResponse } from "../types";
import { formatDate, formatWeight } from "../lib/format";
import { Badge } from "./ui";

export function ContextBar({ result }: { result: AnalysisResponse }) {
  return (
    <p className="context-bar">
      <Badge>
        {result.analysis.persona.name} · {result.request.symbol} ·{" "}
        {formatWeight(result.request.target_weight_pct)}
      </Badge>
      <span>
        {formatDate(result.analysis.period.start)} – {formatDate(result.analysis.period.end)}
      </span>
    </p>
  );
}
