import { ArrowDown, ArrowUp, Check, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import type { Asset, CustomPortfolioAnalysis } from "../types";

interface CustomPortfolioResultsProps {
  result: CustomPortfolioAnalysis;
  assets: Asset[];
  onNewAnalysis: () => void;
}

function formatRate(value: number): string {
  return `${(value * 100).toFixed(2)} %`;
}

function formatDelta(value: number): { text: string; positive: boolean } {
  const positive = value >= 0;
  const text = `${positive ? "+" : ""}${formatRate(value)}`;
  return { text, positive };
}

function MetricCard({
  title,
  before,
  after,
  delta,
  inverse = false
}: {
  title: string;
  before: number;
  after: number;
  delta: number;
  inverse?: boolean;
}) {
  const deltaFormatted = formatDelta(delta);
  const improved = inverse ? !deltaFormatted.positive : deltaFormatted.positive;

  return (
    <div className="p-4 bg-card border border-border rounded-lg space-y-3">
      <div className="font-medium">{title}</div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Avant</div>
          <div className="text-xl font-semibold">{formatRate(before)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Après</div>
          <div className="text-xl font-semibold">{formatRate(after)}</div>
        </div>
      </div>
      <div className={`flex items-center gap-1 text-sm font-medium ${
        improved ? "text-green-500" : "text-red-500"
      }`}>
        {improved ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
        {deltaFormatted.text}
      </div>
    </div>
  );
}

export function CustomPortfolioResults({ result, assets, onNewAnalysis }: CustomPortfolioResultsProps) {
  const assetsBySymbol = useMemo(
    () => Object.fromEntries(assets.map(a => [a.ticker, a])),
    [assets]
  );

  const beforeEntries = useMemo(
    () => Object.entries(result.before.weights_by_asset_pct).sort(([a], [b]) => a.localeCompare(b)),
    [result.before.weights_by_asset_pct]
  );

  const afterEntries = useMemo(
    () => Object.entries(result.after.weights_by_asset_pct).sort(([a], [b]) => a.localeCompare(b)),
    [result.after.weights_by_asset_pct]
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Check className="w-6 h-6 text-green-500" />
            <h1 className="text-2xl font-semibold">Analyse terminée avec succès</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Portefeuille personnalisé de {result.persona.name}
          </p>
        </div>
        <button
          onClick={onNewAnalysis}
          className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors"
        >
          🔄 Nouvelle analyse
        </button>
      </div>

      {/* Metrics Comparison */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Comparaison des performances</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard
            title="Rendement total"
            before={result.before.metrics.total_return}
            after={result.after.metrics.total_return}
            delta={result.delta_after_minus_before.metrics.total_return}
          />
          <MetricCard
            title="Volatilité annualisée"
            before={result.before.metrics.annualized_volatility}
            after={result.after.metrics.annualized_volatility}
            delta={result.delta_after_minus_before.metrics.annualized_volatility}
            inverse
          />
          <MetricCard
            title="Baisse maximale"
            before={result.before.metrics.max_drawdown}
            after={result.after.metrics.max_drawdown}
            delta={result.delta_after_minus_before.metrics.max_drawdown}
            inverse
          />
        </div>
      </div>

      {/* Chart */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Évolution historique</h2>
        <div className="p-4 bg-card border border-border rounded-lg">
          <div className="text-sm text-muted-foreground mb-2">
            Période: {result.period.start} au {result.period.end} ({result.period.common_observations} observations)
          </div>
          <div className="h-64 flex items-center justify-center text-muted-foreground">
            {/* Placeholder for chart - you can integrate a charting library here */}
            <div className="text-center">
              <div className="text-lg mb-2">📈 Graphique d'évolution</div>
              <div className="text-sm">
                Les deux portefeuilles partent de 100 et montrent leur évolution relative
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Weights Details */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Détails des pondérations</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Before */}
          <div className="space-y-2">
            <h3 className="font-medium">Portefeuille initial</h3>
            <div className="space-y-1">
              {beforeEntries.map(([symbol, weight]) => {
                const asset = assetsBySymbol[symbol];
                return (
                  <div key={symbol} className="flex items-center justify-between p-2 bg-card border border-border rounded text-sm">
                    <div>
                      <div className="font-medium">{asset?.name || symbol}</div>
                      <div className="text-xs text-muted-foreground">{symbol}</div>
                    </div>
                    <div className="font-medium">{weight.toFixed(2)}%</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* After */}
          <div className="space-y-2">
            <h3 className="font-medium">Portefeuille personnalisé</h3>
            <div className="space-y-1">
              {afterEntries.map(([symbol, weight]) => {
                const asset = assetsBySymbol[symbol];
                const beforeWeight = result.before.weights_by_asset_pct[symbol] || 0;
                const delta = weight - beforeWeight;
                const isNew = beforeWeight === 0;
                const isRemoved = weight === 0;

                return (
                  <div key={symbol} className={`flex items-center justify-between p-2 border rounded text-sm ${
                    isNew ? "bg-green-500/10 border-green-500/20" :
                    isRemoved ? "bg-red-500/10 border-red-500/20" :
                    "bg-card border-border"
                  }`}>
                    <div>
                      <div className="font-medium">
                        {isNew && "🆕 "}
                        {asset?.name || symbol}
                      </div>
                      <div className="text-xs text-muted-foreground">{symbol}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="font-medium">{weight.toFixed(2)}%</div>
                      {delta !== 0 && (
                        <div className={`flex items-center gap-0.5 text-xs ${
                          delta > 0 ? "text-green-500" : "text-red-500"
                        }`}>
                          {delta > 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                          {Math.abs(delta).toFixed(2)}%
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Methodology Note */}
      <div className="p-4 bg-muted/50 border border-border rounded-lg text-sm text-muted-foreground">
        <div className="font-medium mb-2">Note méthodologique</div>
        <ul className="space-y-1 list-disc list-inside">
          <li>Comparaison historique hypothétique sur la période d'observation commune</li>
          <li>Simulation en {result.currency} avec la stratégie acheter-et-conserver</li>
          <li>Les rendements passés ne présagent pas des rendements futurs</li>
        </ul>
      </div>
    </div>
  );
}
