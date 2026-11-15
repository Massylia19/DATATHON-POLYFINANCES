import { AlertCircle, Check, Loader2, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Asset, Bootstrap, CustomPortfolioResponse, PersonaId } from "../types";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";

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
    <div className="page-stack">
      <section className="page-intro compact">
        <p className="eyebrow">Personnalisation avancée</p>
        <h1>Éditeur de portefeuille</h1>
        <p className="help">
          Modifiez plusieurs actifs simultanément et ajustez tous les poids
        </p>
      </section>

      {/* Persona Selection */}
      <Card>
        <label>Profil d'investisseur</label>
        <div className="persona-selector">
          {data.personas.map(p => (
            <button
              key={p.id}
              type="button"
              onClick={() => setSelectedPersonaId(p.id)}
              aria-pressed={selectedPersonaId === p.id}
            >
              {p.name}
            </button>
          ))}
        </div>
      </Card>

      {persona && (
        <Card className="profile">
          <strong>{persona.name}</strong>
          <p>{persona.objective}</p>
        </Card>
      )}

      {/* Existing Assets */}
      <Card>
        <div className="section-heading">
          <h2>1. Ajuster les poids des actifs existants</h2>
        </div>
        <ul className="holding-list">
          {Object.entries(weights)
            .filter(([_, weight]) => !selectedNewAssets.includes(_) || weight > 0)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([symbol, weight]) => {
              const asset = assetsBySymbol[symbol];
              if (!asset) return null;
              return (
                <li key={symbol} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "12px", alignItems: "center", padding: "12px", border: "1px solid var(--border)", borderRadius: "10px", background: "var(--surface-2)" }}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{asset.name}</div>
                    <div className="help">{asset.ticker} · {asset.asset_class_label}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="0.5"
                      value={weight}
                      onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                      style={{ width: "120px" }}
                    />
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={weight.toFixed(1)}
                      onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                      className="number-input"
                      style={{ width: "70px" }}
                    />
                    <span className="help" style={{ width: "14px" }}>%</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveAsset(symbol)}
                      className="button"
                      style={{ minHeight: "36px", padding: "6px", border: "1px solid var(--error)", color: "var(--error)" }}
                      title="Retirer"
                    >
                      <Trash2 style={{ width: "16px", height: "16px" }} />
                    </button>
                  </div>
                </li>
              );
            })}
        </ul>
      </Card>

      {/* Add New Assets */}
      <Card>
        <div className="section-heading">
          <h2>2. Ajouter de nouveaux actifs</h2>
        </div>
        {availableAssets.length > 0 ? (
          <div style={{ display: "grid", gap: "16px" }}>
            <div className="asset-options">
              {availableAssets.map(asset => (
                <button
                  key={asset.ticker}
                  type="button"
                  onClick={() => handleToggleAsset(asset.ticker)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    ...(selectedNewAssets.includes(asset.ticker) ? {
                      background: "color-mix(in srgb, var(--accent) 12%, var(--surface))",
                      borderColor: "var(--accent)"
                    } : {})
                  }}
                >
                  <div style={{
                    width: "20px",
                    height: "20px",
                    border: "2px solid var(--border)",
                    borderRadius: "4px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    ...(selectedNewAssets.includes(asset.ticker) ? {
                      background: "var(--accent)",
                      borderColor: "var(--accent)"
                    } : {})
                  }}>
                    {selectedNewAssets.includes(asset.ticker) && (
                      <Check style={{ width: "14px", height: "14px", color: "var(--accent-text)" }} />
                    )}
                  </div>
                  <div style={{ flex: 1, textAlign: "left" }}>
                    <div style={{ fontWeight: 700 }}>{asset.name}</div>
                    <span>{asset.ticker} · {asset.asset_class_label}</span>
                  </div>
                </button>
              ))}
            </div>

            {selectedNewAssets.length > 0 && (
              <div style={{ display: "grid", gap: "12px" }}>
                <p className="help">
                  Définissez les pondérations pour les nouveaux actifs
                </p>
                <ul className="holding-list">
                  {selectedNewAssets.map(symbol => {
                    const asset = assetsBySymbol[symbol];
                    const weight = weights[symbol] || 0;
                    return (
                      <li key={symbol} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "12px", alignItems: "center", padding: "12px", border: "2px solid var(--accent)", borderRadius: "10px", background: "var(--surface-2)" }}>
                        <div>
                          <div style={{ fontWeight: 700 }}>{asset.name}</div>
                          <div className="help">{asset.ticker} · {asset.asset_class_label}</div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <input
                            type="range"
                            min="0.5"
                            max="50"
                            step="0.5"
                            value={weight}
                            onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                            style={{ width: "120px" }}
                          />
                          <input
                            type="number"
                            min="0.5"
                            max="50"
                            step="0.5"
                            value={weight.toFixed(1)}
                            onChange={e => handleWeightChange(symbol, Number(e.target.value))}
                            className="number-input"
                            style={{ width: "70px" }}
                          />
                          <span className="help" style={{ width: "14px" }}>%</span>
                          <button
                            type="button"
                            onClick={() => handleRemoveAsset(symbol)}
                            className="button"
                            style={{ minHeight: "36px", padding: "6px", border: "1px solid var(--error)", color: "var(--error)" }}
                            title="Retirer"
                          >
                            <X style={{ width: "16px", height: "16px" }} />
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="help" style={{ padding: "12px", border: "1px solid var(--border)", borderRadius: "10px", background: "var(--surface-2)" }}>
            Tous les actifs disponibles sont déjà dans le portefeuille.
          </p>
        )}
      </Card>

      {/* Summary */}
      <Card>
        <div className="section-heading">
          <h2>3. Résumé du nouveau portefeuille</h2>
        </div>
        <div style={{ display: "grid", gap: "16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
            <div className="metric-card">
              <div className="metric-head">
                <h3>Total des pondérations</h3>
              </div>
              <div className="metric-after">{totalWeight.toFixed(1)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-head">
                <h3>État</h3>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {isBalanced ? (
                  <>
                    <Check style={{ width: "20px", height: "20px", color: "var(--accent)" }} />
                    <span style={{ fontWeight: 700, color: "var(--accent)" }}>Équilibré</span>
                  </>
                ) : (
                  <>
                    <AlertCircle style={{ width: "20px", height: "20px", color: "var(--warning)" }} />
                    <span style={{ fontWeight: 700, color: "var(--warning)" }}>
                      Écart: {(totalWeight - 100) > 0 ? "+" : ""}{(totalWeight - 100).toFixed(1)}%
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className="metric-card">
              <Button type="button" onClick={handleReset} style={{ width: "100%" }}>
                Réinitialiser
              </Button>
            </div>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", border: "1px solid var(--border)", borderRadius: "10px", background: "var(--surface-2)", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={autoNormalize}
              onChange={e => setAutoNormalize(e.target.checked)}
              style={{ width: "18px", height: "18px" }}
            />
            <span>Normaliser automatiquement à 100%</span>
          </label>

          {error && (
            <div className="error">
              {error}
            </div>
          )}

          <Button
            type="button"
            className="primary"
            onClick={handleAnalyze}
            disabled={!canAnalyze || analyzing}
            style={{ width: "100%", minHeight: "48px" }}
          >
            {analyzing ? (
              <>
                <Loader2 style={{ width: "20px", height: "20px" }} className="spinner" />
                Analyse en cours...
              </>
            ) : (
              <>Analyser ce portefeuille</>
            )}
          </Button>

          {!canAnalyze && !autoNormalize && (
            <p className="help" style={{ textAlign: "center" }}>
              Veuillez équilibrer le portefeuille à 100% ou activer la normalisation automatique.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
