import { useState } from "react";
import type { Asset, Persona, Portfolio, ScenarioRequest } from "../../types";
import { formatWeight } from "../../lib/format";
import { Button, Card, Spinner } from "../../components/ui";

export function ScenarioPanel({ personas, portfolio, assets, draft, busy, onDraft, onAnalyze, onInterpret }: { personas: Persona[]; portfolio: Portfolio; assets: Asset[]; draft: ScenarioRequest; busy: boolean; onDraft: (next: ScenarioRequest) => void; onAnalyze: () => void; onInterpret: (text: string) => void }) {
  const persona = personas.find(p => p.id === draft.persona_id)!;
  const held = new Set(portfolio.positions.map(p => p.symbol));
  const available = assets.filter(a => !held.has(a.ticker));
  return <Card className="scenario-panel"><h2>Votre scénario</h2>
    <fieldset><legend>Profil</legend><div className="persona-selector">{personas.map(p => <button key={p.id} type="button" aria-pressed={draft.persona_id === p.id} onClick={() => onDraft({ ...draft, persona_id: p.id })}>{p.name}</button>)}</div></fieldset>
    <div className="profile"><span>Objectif</span><strong>{persona.objective}</strong><p>{persona.horizon_years_min}{persona.horizon_years_max ? `–${persona.horizon_years_max}` : " ans et plus"}{persona.horizon_years_max ? " ans" : ""} · {persona.risk_level.replaceAll("_", " ")}</p></div>
    <h3>Répartition de départ</h3><div className="allocations">{portfolio.positions.map(position => <div className="allocation" key={position.symbol}><span>{position.symbol}</span><div><i style={{ width: `${position.weight_pct}%` }} /></div><b>{formatWeight(position.weight_pct)}</b></div>)}</div>
    <hr /><label>Actif à ajouter<select value={draft.symbol} onChange={e => onDraft({ ...draft, symbol: e.target.value })}>{available.map(asset => <option key={asset.ticker} value={asset.ticker}>{asset.name} — {asset.ticker}</option>)}</select></label>
    <label>Part du portefeuille <span className="weight-value">{formatWeight(draft.target_weight_pct)}</span><input type="range" min="1" max="50" step="0.5" value={draft.target_weight_pct} onChange={e => onDraft({ ...draft, target_weight_pct: Number(e.target.value) })} /><input className="number-input" aria-label="Part numérique du portefeuille" type="number" min="1" max="50" step="0.5" value={draft.target_weight_pct} onChange={e => onDraft({ ...draft, target_weight_pct: Number(e.target.value) })} /></label>
    <p className="help">Les autres positions diminuent proportionnellement.</p><Button className="primary" disabled={busy} onClick={onAnalyze}>{busy ? <><Spinner />Analyse en cours…</> : "Analyser le scénario"}</Button>
    <details className="natural"><summary>Décrire ma demande avec mes mots</summary><NaturalForm busy={busy} onSubmit={onInterpret} /></details>
  </Card>;
}

function NaturalForm({ busy, onSubmit }: { busy: boolean; onSubmit: (text: string) => void }) {
  const [text, setText] = useState("");
  return <form onSubmit={event => { event.preventDefault(); if (text.trim()) onSubmit(text.trim()); }}>
    <label>Votre demande<input value={text} onChange={event => setText(event.target.value)} maxLength={500} placeholder="Pour Amira, tester 15 % de NVIDIA." /></label>
    <Button disabled={busy || !text.trim()}>Comprendre la demande</Button>
  </form>;
}
