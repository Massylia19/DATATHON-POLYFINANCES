import { AlertTriangle, Briefcase, Clock, Gauge, PenLine, PieChart, Play, Target } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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
import { Button, Card, InfoTip, Spinner } from "../../components/ui";

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

  const barRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const openPopups = () =>
      Array.from(barRef.current?.querySelectorAll<HTMLDetailsElement>("details.inline-pop[open]") ?? []);
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      openPopups().forEach(popup => {
        if (!popup.contains(target)) popup.open = false;
      });
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      openPopups().forEach(popup => {
        popup.open = false;
        popup.querySelector("summary")?.focus();
      });
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

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

  const horizon = `${persona.horizon_years_min}${persona.horizon_years_max ? `–${persona.horizon_years_max} ans` : " ans et plus"}`;

  return (
    <Card className="scenario-panel scenario-bar" ref={barRef}>
      <h2 className="sr-only">Choisir une situation</h2>
      <div className="persona-row">
        <fieldset className="persona-fieldset">
          <legend className="sr-only">Profil à explorer</legend>
          <div className="persona-selector">
            {personas.map(item => (
              <button
                key={item.id}
                type="button"
                aria-pressed={draft.persona_id === item.id}
                onClick={() => onSelectPersona(item.id)}
              >
                <span className={`avatar avatar-${item.id}`} aria-hidden="true">{item.name.charAt(0)}</span>
                {item.name}
              </button>
            ))}
          </div>
        </fieldset>
        <div className="profile-strip">
          <span className="profile-chip"><Target aria-hidden="true" />{persona.objective}</span>
          <span className="profile-chip"><Clock aria-hidden="true" />{horizon}</span>
          <span className={`profile-chip risk-${persona.risk_level}`}><Gauge aria-hidden="true" />{formatRisk(persona)}</span>
          <details className="portfolio-details inline-pop">
            <summary><Briefcase aria-hidden="true" />Portefeuille de départ</summary>
            <div className="pop-body">
              <ul className="holding-list">
                {portfolio.positions.map(position => (
                  <li key={position.symbol}>
                    <span>{positionLabel(position.symbol, assets)}</span>
                    <strong>{formatWeight(position.weight_pct)}</strong>
                  </li>
                ))}
              </ul>
              <p className="help"><b>Préférences :</b> {formatPreferences(persona.preferences)}</p>
              <p className="help">{portfolio.construction_note}</p>
              <p className="help">
                <AlertTriangle aria-hidden="true" className="inline-icon" />
                Non renseignés : la capacité à absorber une perte, les besoins de
                liquidités à court terme et les retraits prévus.
              </p>
            </div>
          </details>
        </div>
      </div>

      <form
        className="scenario-form"
        onSubmit={event => {
          event.preventDefault();
          if (validForm) onAnalyze();
        }}
      >
        <h2 className="sr-only">Décrire un changement</h2>
        <div className="field asset-field">
        <label htmlFor="asset-search">Actif à ajouter</label>
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
        <p id="asset-status" className={chosenAsset ? "sr-only" : "help"}>
          {chosenAsset
            ? chosenAsset.asset_class_label
            : assetQuery
              ? "Choisissez un placement dans la liste."
              : "Tapez un nom ou un symbole pour rechercher."}
        </p>
        <span id="asset-help" className="sr-only">Un actif est un placement, par exemple une action ou un fonds.</span>
        </div>

        <div className="field weight-field">
        <span className="label-row">
          <label htmlFor="weight-slider">Part du nouvel actif (%)</label>
          <InfoTip label="Comment la part est financée" align="left">
            Pour faire de la place, les autres placements sont réduits dans les mêmes proportions. De 1 % à 50 %, par pas de 0,5 %.
          </InfoTip>
        </span>
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
        <p id="weight-help" className={validWeight ? "sr-only" : "field-error"}>
          {validWeight
            ? "Les autres placements sont réduits dans les mêmes proportions."
            : "Saisissez un nombre de 1 % à 50 %, par pas de 0,5 %."}
        </p>
        </div>

        <div className="field action-field">
          <Button className="primary analyze-button" type="submit" disabled={busy || !validForm || !formValid}>
            {busy ? <><Spinner />Calcul en cours…</> : <><Play aria-hidden="true" />Analyser le scénario</>}
          </Button>
        </div>

        <details className="allocation-preview inline-pop" aria-live="polite">
          <summary><PieChart aria-hidden="true" />Aperçu</summary>
          <div className="pop-body">
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
          </div>
        </details>
      </form>

      <details className="natural">
        <summary><PenLine aria-hidden="true" className="inline-icon" />Décrire une demande avec vos mots (facultatif)</summary>
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
