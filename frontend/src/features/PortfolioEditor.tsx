import { AlertCircle, Check, Loader2, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Asset, Bootstrap, CustomPortfolioResponse, PersonaId, Portfolio } from "../types";
import { api } from "../lib/api";

interface PortfolioEditorProps {
  data: Bootstrap;
  onResult: (result: CustomPortfolioResponse) => void;
}

export function PortfolioEditor({ data, onResult }: PortfolioEditorProps) {
  const [selectedPersonaId, setSelectedPersonaId] = useState<PersonaId>("amira");
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [availableAssets, setAvailableAssets] = useState<Asset[]>([]);
  const [selectedNewAssets, setSelectedNewAssets] = useState<string[]>([]);
  const [autoNormalize, setAutoNormalize] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  const persona = useMemo(
    () => data.personas.find(p => p.id === selectedPersonaId),
    [data.personas, selectedPersonaId]
  );

  const initialPortfolio = useMemo(
    () => data.portfolios.find(p => p.persona_id === selectedPersonaId),
    [data.portfolios, selectedPersonaId]
  );

  const assetsBySymbol = useMemo(
    () => Object.fromEntries(data.assets.map(a => [a.ticker, a])),
    [data.assets]
  );

  // Initialize weights when persona changes
  useEffect(() => {
    if (!initialPortfolio) return;
    const initialWeights: Record<string, number> = {};
    initialPortfolio.positions.forEach(pos => {
      initialWeights[pos.symbol] = pos.weight_pct;
    });
    setWeights(initialWeights);
    setSelectedNewAssets([]);
    setError("");
  }, [initialPortfolio]);

  // Update available assets
  useEffect(() => {
    const currentSymbols = new Set(Object.keys(weights).filter(s => weights[s] > 0));
    setAvailableAssets(data.assets.filter(a => !currentSymbols.has(a.ticker)));
  }, [data.assets, weights]);

  const handleWeightChange = useCallback((symbol: string, value: number) => {
    setWeights(prev => ({ ...prev, [symbol]: Math.max(0, Math.min(100, value)) }));
  }, []);

  const handleRemoveAsset = useCallback((symbol: string) => {
    setWeights(prev => {
      const next = { ...prev };
      delete next[symbol];
      return next;
    });
    setSelectedNewAssets(prev => prev.filter(s => s !== symbol));
  }, []);

  const handleAddAsset = useCallback((symbol: string) => {
    if (!selectedNewAssets.includes(symbol)) {
      setSelectedNewAssets(prev => [...prev, symbol]);
      setWeights(prev => ({ ...prev, [symbol]: 5.0 }));
    }
  }, [selectedNewAssets]);

  const handleToggleAsset = useCallback((symbol: string) => {
    if (selectedNewAssets.includes(symbol)) {
      handleRemoveAsset(symbol);
    } else {
      handleAddAsset(symbol);
    }
  }, [selectedNewAssets, handleAddAsset, handleRemoveAsset]);

  const totalWeight = useMemo(
    () => Object.values(weights).reduce((sum, w) => sum + w, 0),
    [weights]
  );

  const normalizedWeights = useMemo(() => {
    if (!autoNormalize || Math.abs(totalWeight - 100) < 0.01) return weights;
    if (totalWeight === 0) return weights;
    const factor = 100 / totalWeight;
    return Object.fromEntries(
      Object.entries(weights).map(([symbol, weight]) => [symbol, weight * factor])
    );
  }, [weights, totalWeight, autoNormalize]);

  const canAnalyze = useMemo(() => {
    if (totalWeight === 0) return false;
    if (autoNormalize) return true;
    return Math.abs(totalWeight - 100) < 0.01;
  }, [totalWeight, autoNormalize]);

  const handleAnalyze = useCallback(async () => {
    if (!canAnalyze) return;
    setAnalyzing(true);
    setError("");

    try {
      const result = await api.analyzeCustomPortfolio({
        persona_id: selectedPersonaId,
        weights: normalizedWeights,
      });
      onResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue");
    } finally {
      setAnalyzing(false);
    }
  }, [canAnalyze, selectedPersonaId, normalizedWeights, onResult]);

  const handleReset = useCallback(() => {
    if (!initialPortfolio) return;
    const initialWeights: Record<string, number> = {};
    initialPortfolio.positions.forEach(pos => {
      initialWeights[pos.symbol] = pos.weight_pct;
    });
    setWeights(initialWeights);
    setSelectedNewAssets([]);
    setError("");
  }, [initialPortfolio]);

  const weightDelta = Math.abs(totalWeight - 100);
  const isBalanced = weightDelta < 0.01;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold">Éditeur de portefeuille</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Modifiez plusieurs actifs simultanément et ajustez tous les poids
        </p>
      </div>

      {/* Persona Selection */}
      <div>
        <label className="block text-sm font-medium mb-2">Profil d'investisseur</label>
        <div className="flex flex-wrap gap-2">
          {data.personas.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedPersonaId(p.id)}
              className={`px-4 py-2 rounded-lg border transition-colors ${selectedPersonaId === p.id
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-card text-card-foreground border-border hover:bg-accent"
                }`}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {persona && (
        <div className="p-4 bg-card border border-border rounded-lg">
          <div className="text-sm">
            <div className="font-medium">{persona.name}</div>
            <div className="text-muted-foreground">{persona.objective}</div>
          </div>
        </div>
      )}

      {/* Existing Assets */}
      <div>
        <h2 className="text-xl font-semibold mb-4">1. Ajuster les poids des actifs existants</h2>
        <div className="space-y-4">
          {Object.entries(weights)
            .filter(([_, weight]) => !selectedNewAssets.includes(_) || weight > 0)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([symbol, weight]) => {
              const asset = assetsBySymbol[symbol];
              if (!asset) return null;
              return (
                <div key={symbol} className="flex items-center gap-4 p-4 bg-card border border-border rounded-lg">
                  <div className="flex-1">
                    <div className="font-medium">{asset.name}</div>
                    <div className="text-sm text-muted-foreground">{asset.ticker} · {asset.asset_class_label}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="0.5"
                      value={weight}
                      onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                      className="w-32"
                    />
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={weight.toFixed(1)}
                      onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                      className="w-20 px-2 py-1 bg-background border border-border rounded text-right"
                    />
                    <span className="text-sm w-4">%</span>
                    <button
                      onClick={() => handleRemoveAsset(symbol)}
                      className="p-2 hover:bg-destructive/10 text-destructive rounded transition-colors"
                      title="Retirer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Add New Assets */}
      <div>
        <h2 className="text-xl font-semibold mb-4">2. Ajouter de nouveaux actifs</h2>
        {availableAssets.length > 0 ? (
          <div className="space-y-4">
            <div className="max-h-60 overflow-y-auto space-y-2 p-2 bg-card/50 border border-border rounded-lg">
              {availableAssets.map(asset => (
                <button
                  key={asset.ticker}
                  onClick={() => handleToggleAsset(asset.ticker)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-colors text-left ${selectedNewAssets.includes(asset.ticker)
                    ? "bg-primary/10 border-primary"
                    : "bg-card border-border hover:bg-accent"
                    }`}
                >
                  <div className={`w-5 h-5 rounded border flex items-center justify-center ${selectedNewAssets.includes(asset.ticker)
                    ? "bg-primary border-primary"
                    : "border-border"
                    }`}>
                    {selectedNewAssets.includes(asset.ticker) && (
                      <Check className="w-3 h-3 text-primary-foreground" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{asset.name}</div>
                    <div className="text-sm text-muted-foreground">{asset.ticker} · {asset.asset_class_label}</div>
                  </div>
                </button>
              ))}
            </div>

            {selectedNewAssets.length > 0 && (
              <div className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  Définissez les pondérations pour les nouveaux actifs
                </div>
                {selectedNewAssets.map(symbol => {
                  const asset = assetsBySymbol[symbol];
                  const weight = weights[symbol] || 0;
                  return (
                    <div key={symbol} className="flex items-center gap-4 p-4 bg-card border border-primary/20 rounded-lg">
                      <div className="flex-1">
                        <div className="font-medium">{asset.name}</div>
                        <div className="text-sm text-muted-foreground">{asset.ticker} · {asset.asset_class_label}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min="0.5"
                          max="50"
                          step="0.5"
                          value={weight}
                          onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                          className="w-32"
                        />
                        <input
                          type="number"
                          min="0.5"
                          max="50"
                          step="0.5"
                          value={weight.toFixed(1)}
                          onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                          className="w-20 px-2 py-1 bg-background border border-border rounded text-right"
                        />
                        <span className="text-sm w-4">%</span>
                        <button
                          onClick={() => handleRemoveAsset(symbol)}
                          className="p-2 hover:bg-destructive/10 text-destructive rounded transition-colors"
                          title="Retirer"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground p-4 bg-card border border-border rounded-lg">
            Tous les actifs disponibles sont déjà dans le portefeuille.
          </p>
        )}
      </div>

      {/* Summary */}
      <div>
        <h2 className="text-xl font-semibold mb-4">3. Résumé du nouveau portefeuille</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 bg-card border border-border rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Total des pondérations</div>
              <div className="text-2xl font-semibold">{totalWeight.toFixed(1)}%</div>
            </div>
            <div className="p-4 bg-card border border-border rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">État</div>
              <div className="flex items-center gap-2">
                {isBalanced ? (
                  <>
                    <Check className="w-5 h-5 text-green-500" />
                    <span className="font-semibold text-green-500">Équilibré</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-5 h-5 text-yellow-500" />
                    <span className="font-semibold text-yellow-500">
                      Écart: {weightDelta > 0 ? "+" : ""}{(totalWeight - 100).toFixed(1)}%
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className="p-4 bg-card border border-border rounded-lg">
              <button
                onClick={handleReset}
                className="w-full px-4 py-2 bg-secondary text-secondary-foreground rounded hover:bg-secondary/80 transition-colors"
              >
                Réinitialiser
              </button>
            </div>
          </div>

          <label className="flex items-center gap-2 p-4 bg-card border border-border rounded-lg cursor-pointer">
            <input
              type="checkbox"
              checked={autoNormalize}
              onChange={e => setAutoNormalize(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm">Normaliser automatiquement à 100%</span>
          </label>

          {error && (
            <div className="p-4 bg-destructive/10 border border-destructive text-destructive rounded-lg">
              {error}
            </div>
          )}

          <button
            onClick={handleAnalyze}
            disabled={!canAnalyze || analyzing}
            className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {analyzing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Analyse en cours...
              </>
            ) : (
              <>Analyser ce portefeuille</>
            )}
          </button>

          {!canAnalyze && !autoNormalize && (
            <p className="text-sm text-muted-foreground text-center">
              Veuillez équilibrer le portefeuille à 100% ou activer la normalisation automatique.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
