import { useEffect, useMemo, useState } from "react";
import type {
  Asset,
  InterpretResponse,
  Persona,
  Portfolio,
  ScenarioRequest,
} from "../../types";
import { formatWeight, scenarioKey } from "../../lib/format";
import {
  formatPreferences,
  formatRisk,
  positionLabel,
  previewAllocation,
} from "../../lib/presentation";
import { Button, Card, Spinner } from "../../components/ui";

interface ScenarioPanelProps {
  personas: Persona[];
  portfolio: Portfolio;
  assets: Asset[];
  draft: ScenarioRequest;
  busy: boolean;
  interpreting: boolean;
  interpretation: InterpretResponse | null;
  formValid: boolean;
  onValidityChange: (valid: boolean) => void;
  onDraft: (next: ScenarioRequest) => void;
  onSelectPersona: (personaId: Persona["id"]) => void;
  onAnalyze: () => void;
  onInterpret: (text: string) => void;
  onApplyProposal: (request: ScenarioRequest) => void;
}

function isValidWeightText(value: string): boolean {
  if (!value.trim()) return false;
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed) || parsed < 1 || parsed > 50) return false;
  return Math.abs((parsed - 1) * 2 - Math.round((parsed - 1) * 2)) < 1e-9;
}

function matchingAsset(value: string, assets: Asset[]): Asset | undefined {
  const normalized = value.trim().toLocaleLowerCase("fr-CA");
  return assets.find(asset =>
    [asset.ticker, asset.name, `${asset.name} — ${asset.ticker}`]
      .some(label => label.toLocaleLowerCase("fr-CA") === normalized),
  );
}

export function ScenarioPanel({
  personas,
  portfolio,
  assets,
  draft,
  busy,
  interpreting,
  interpretation,
  formValid,
  onValidityChange,
  onDraft,
  onSelectPersona,
  onAnalyze,
  onInterpret,
  onApplyProposal,
}: ScenarioPanelProps) {
  const persona = personas.find(item => item.id === draft.persona_id)!;
  const available = useMemo(
    () => {
      const held = new Set(portfolio.positions.map(position => position.symbol));
      return assets.filter(asset => !held.has(asset.ticker));
    },
    [assets, portfolio.positions],
  );
  const draftKey = scenarioKey(draft.persona_id, draft.symbol, draft.target_weight_pct);
  const selectedAsset = available.find(asset => asset.ticker === draft.symbol);
  const [assetEdit, setAssetEdit] = useState<{ key: string; value: string } | null>(null);
  const [weightEdit, setWeightEdit] = useState<{ key: string; value: string } | null>(null);
  const assetQuery = assetEdit?.key === draftKey
    ? assetEdit.value
    : selectedAsset ? `${selectedAsset.name} — ${selectedAsset.ticker}` : "";
  const weightText = weightEdit?.key === draftKey
    ? weightEdit.value
    : String(draft.target_weight_pct);
  const [naturalRequest, setNaturalRequest] = useState("");

  const chosenAsset = matchingAsset(assetQuery, available);
  const validWeight = isValidWeightText(weightText);
  const validForm = Boolean(chosenAsset && validWeight);

  useEffect(() => {
    onValidityChange(validForm);
  }, [validForm, onValidityChange]);

  const preview = useMemo(
    () => validForm && chosenAsset
      ? previewAllocation(
          portfolio.positions,
          chosenAsset.ticker,
          Number(weightText.replace(",", ".")),
          assets,
        )
      : [],
    [assets, chosenAsset, portfolio.positions, validForm, weightText],
  );
  const proposal = interpretation?.status === "ready"
    ? interpretation.request
    : null;
  const proposedPersona = proposal
    ? personas.find(item => item.id === proposal.persona_id)
    : null;
  const proposedAsset = proposal
    ? assets.find(item => item.ticker === proposal.symbol)
    : null;

  const updateWeight = (value: string) => {
    setWeightEdit({ key: draftKey, value });
    if (isValidWeightText(value)) {
      onDraft({ ...draft, target_weight_pct: Number(value.replace(",", ".")) });
    }
  };

  return (
    <Card className="scenario-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Étape 1 · Profil fictif</p>
          <h2>Choisir une situation</h2>
        </div>
      </div>
      <p className="help">
        Amira, Mateo et Robert sont des profils de démonstration; ils ne sont
        pas des comptes clients ni des recommandations.
      </p>
      <fieldset>
        <legend>Profil à explorer</legend>
        <div className="persona-selector">
          {personas.map(item => (
            <button
              key={item.id}
              type="button"
              aria-pressed={draft.persona_id === item.id}
              onClick={() => onSelectPersona(item.id)}
            >
              {item.name}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="profile">
        <span>{formatRisk(persona)}</span>
        <strong>{persona.objective}</strong>
        <p>
          Horizon : {persona.horizon_years_min}
          {persona.horizon_years_max
            ? `–${persona.horizon_years_max} ans`
            : " ans et plus"}
        </p>
        <p><b>Préférences :</b> {formatPreferences(persona.preferences)}</p>
      </div>

      <details className="portfolio-details">
        <summary>Voir son portefeuille de départ</summary>
        <ul className="holding-list">
          {portfolio.positions.map(position => (
            <li key={position.symbol}>
              <span>{positionLabel(position.symbol, assets)}</span>
              <strong>{formatWeight(position.weight_pct)}</strong>
            </li>
          ))}
        </ul>
        <p className="help">{portfolio.construction_note}</p>
      </details>

      <section className="unknowns-note">
        <h3>Ce que nous ne savons pas</h3>
        <p>
          La capacité à absorber une perte, les besoins de liquidités à court
          terme et les retraits prévus ne sont pas renseignés.
        </p>
      </section>

      <form
        className="scenario-form"
        onSubmit={event => {
          event.preventDefault();
          if (validForm) onAnalyze();
        }}
      >
        <p className="eyebrow">Étape 2 · Simulation</p>
        <h2>Décrire un changement</h2>
        <label htmlFor="asset-search">Actif à ajouter</label>
        <p className="help" id="asset-help">Un actif est un placement, par exemple une action ou un fonds.</p>
        <input
          id="asset-search"
          role="combobox"
          aria-autocomplete="list"
          aria-controls="asset-options"
          aria-expanded={Boolean(assetQuery && !chosenAsset)}
          aria-invalid={assetQuery.length > 0 && !chosenAsset}
          aria-describedby="asset-help asset-status"
          value={assetQuery}
          onChange={event => {
            const value = event.target.value;
            setAssetEdit({ key: draftKey, value });
            const match = matchingAsset(value, available);
            if (match) onDraft({ ...draft, symbol: match.ticker });
          }}
          placeholder="Rechercher par nom ou symbole"
        />
        <div id="asset-options" className="asset-options" role="listbox" aria-label="Placements disponibles">
          {assetQuery && !chosenAsset && available
            .filter(asset =>
              `${asset.name} ${asset.ticker}`
                .toLocaleLowerCase("fr-CA")
                .includes(assetQuery.toLocaleLowerCase("fr-CA")),
            )
            .slice(0, 8)
            .map(asset => (
              <button
                type="button"
                role="option"
                aria-selected={false}
                key={asset.ticker}
                onClick={() => {
                  setAssetEdit({ key: draftKey, value: `${asset.name} — ${asset.ticker}` });
                  onDraft({ ...draft, symbol: asset.ticker });
                }}
              >
                {asset.name} — {asset.ticker}
                <span>{asset.asset_class_label}</span>
              </button>
            ))}
        </div>
        <p id="asset-status" className="help">
          {chosenAsset
            ? chosenAsset.asset_class_label
            : assetQuery
              ? "Choisissez un placement dans la liste."
              : "Tapez un nom ou un symbole pour rechercher."}
        </p>

        <label htmlFor="weight-slider">Place du nouvel actif dans le portefeuille (%)</label>
        <div className="weight-controls">
          <input
            id="weight-slider"
            type="range"
            min="1"
            max="50"
            step="0.5"
            value={validWeight ? Number(weightText.replace(",", ".")) : draft.target_weight_pct}
            onChange={event => updateWeight(event.target.value)}
            aria-label="Régler la part du nouvel actif"
          />
          <input
            className="number-input"
            aria-label="Saisir la part du nouvel actif en pourcentage"
            type="number"
            min="1"
            max="50"
            step="0.5"
            value={weightText}
            aria-invalid={!validWeight}
            aria-describedby="weight-help"
            onChange={event => updateWeight(event.target.value)}
          />
        </div>
        <p id="weight-help" className={validWeight ? "help" : "field-error"}>
          {validWeight
            ? "De 1 % à 50 %, par pas de 0,5 %."
            : "Saisissez un nombre de 1 % à 50 %, par pas de 0,5 %."}
        </p>
        <p className="help">
          Pour faire de la place au nouvel actif, les placements de départ sont
          réduits dans les mêmes proportions.
        </p>

        <section className="allocation-preview" aria-live="polite">
          <h3>Aperçu des pondérations</h3>
          {validForm ? (
            <>
              {preview.map(item => (
                <div className="allocation" key={item.symbol}>
                  <span>{item.label}</span>
                  <div aria-hidden="true">
                    <i style={{ width: `${item.after}%` }} />
                  </div>
                  <b>
                    {item.before > 0
                      ? `${formatWeight(item.before)} → ${formatWeight(item.after)}`
                      : formatWeight(item.after)}
                  </b>
                </div>
              ))}
              <p className="help">Aperçu de l’allocation, pas un résultat historique.</p>
            </>
          ) : (
            <p className="help">Choisissez un placement et une proportion valide.</p>
          )}
        </section>
        <Button className="primary" type="submit" disabled={busy || !validForm || !formValid}>
          {busy ? <><Spinner />Calcul en cours…</> : "Analyser le scénario"}
        </Button>
      </form>

      <details className="natural">
        <summary>Décrire une demande avec vos mots (facultatif)</summary>
        <form
          onSubmit={event => {
            event.preventDefault();
            if (!interpreting && naturalRequest.trim()) onInterpret(naturalRequest.trim());
          }}
        >
          <label htmlFor="natural-request">Votre demande</label>
          <input
            id="natural-request"
            maxLength={500}
            value={naturalRequest}
            onChange={event => setNaturalRequest(event.target.value)}
            placeholder="Pour Amira, tester 15 % de NVIDIA."
          />
          <Button className="primary" type="submit" disabled={interpreting || !naturalRequest.trim()}>
            {interpreting ? <><Spinner />Compréhension…</> : "Comprendre la demande"}
          </Button>
        </form>
        {interpretation && interpretation.status !== "ready" && (
          <p className={interpretation.status === "error" ? "field-error" : "notice"} role="status">
            {interpretation.status === "error"
              ? interpretation.error.message
              : interpretation.message}
          </p>
        )}
        {proposal && proposedPersona && (
          <div className="proposal" role="status">
            <p>
              Demande comprise : <b>{proposedPersona.name}</b> ·{" "}
              <b>{proposedAsset?.name ?? proposal.symbol} — {proposal.symbol}</b> ·{" "}
              <b>{formatWeight(proposal.target_weight_pct)}</b>
            </p>
            <p>Vérifiez ces paramètres avant de lancer les calculs.</p>
            <Button className="primary" type="button" onClick={() => onApplyProposal(proposal)}>
              Appliquer au formulaire
            </Button>
          </div>
        )}
      </details>
    </Card>
  );
}
