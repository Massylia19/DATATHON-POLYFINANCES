import { AlertTriangle, ArrowRight, Clock, MessageCircleQuestion, Play, ShieldCheck, SlidersHorizontal, Users } from "lucide-react";
import type { Asset, Persona, Portfolio, SavedScenario, Scenario } from "../types";
import { formatDate, formatWeight } from "../lib/format";
import {
  formatMissingInformation,
  formatPreferences,
  formatRisk,
  positionLabel,
} from "../lib/presentation";
import { Button, Card } from "../components/ui";

interface PageContext {
  personas: Persona[];
  portfolios: Portfolio[];
  scenarios: Scenario[];
  assets: Asset[];
  onChoose: (persona: Persona) => void;
}

const demoQuestions: Record<string, string> = {
  amira: "L’ajout de NVIDIA renforce-t-il une exposition déjà présente ?",
  mateo: "Les résultats financiers suffisent-ils à vérifier ses préférences ESG ?",
  robert: "Quel compromis un ajout de Tesla crée-t-il pour la préservation du capital ?",
};

function ProfileCard({
  persona,
  portfolio,
  assets,
  scenario,
  onChoose,
}: {
  persona: Persona;
  portfolio: Portfolio;
  assets: Asset[];
  scenario: Scenario;
  onChoose: () => void;
}) {
  const missing = formatMissingInformation(persona.missing_information);
  const horizon = `${persona.horizon_years_min}${persona.horizon_years_max ? `–${persona.horizon_years_max} ans` : " ans et plus"}`;
  return (
    <Card className="persona-card">
      <header className="persona-card-head">
        <span className={`avatar avatar-${persona.id}`} aria-hidden="true">{persona.name.charAt(0)}</span>
        <h2>{persona.name}</h2>
        <span className={`risk-chip risk-${persona.risk_level}`}>{formatRisk(persona).replace(" déclaré", "")}</span>
      </header>
      <p className="persona-objective">{persona.objective}</p>
      <div className="persona-chips">
        <span className="profile-chip"><Clock aria-hidden="true" />{horizon}</span>
        <span className="profile-chip"><Play aria-hidden="true" />{scenario.symbol} · {formatWeight(scenario.target_weight_pct)}</span>
      </div>
      <ul className="tag-list" aria-label={`Préférences : ${formatPreferences(persona.preferences)}`}>
        {persona.preferences.map(item => <li key={item}>{item}</li>)}
      </ul>
      <Button className="primary" type="button" onClick={onChoose}>
        Explorer le profil de {persona.name}
      </Button>
      <details className="persona-details">
        <summary>Détails</summary>
        <p className="demo-question"><b>À explorer :</b> {demoQuestions[persona.id]}</p>
        <p className="help"><b>Préférences :</b> {formatPreferences(persona.preferences)}</p>
        <p className="details-label">Portefeuille de départ</p>
        <ul className="holding-bars">
          {portfolio.positions.map(position => (
            <li key={position.symbol}>
              <span title={positionLabel(position.symbol, assets)}><b>{position.symbol}</b></span>
              <i aria-hidden="true"><i style={{ width: `${Math.min(position.weight_pct, 100)}%` }} /></i>
              <strong>{formatWeight(position.weight_pct)}</strong>
            </li>
          ))}
        </ul>
        <p className="help">
          <AlertTriangle aria-hidden="true" className="inline-icon" />
          Non renseignés : {missing.join(" · ")}.
        </p>
      </details>
    </Card>
  );
}

function profileItems(context: PageContext) {
  return context.personas.map(persona => ({
    persona,
    portfolio: context.portfolios.find(item => item.persona_id === persona.id)!,
    scenario: context.scenarios.find(item => item.persona_id === persona.id)!,
  }));
}

const overviewSteps = [
  { page: "simulation", icon: SlidersHorizontal, title: "Simuler", text: "Ajoutez un placement, voyez l’effet." },
  { page: "coherence", icon: ShieldCheck, title: "Vérifier", text: "Repérez les points de vigilance pour le profil." },
  { page: "assistant", icon: MessageCircleQuestion, title: "Comprendre", text: "Posez une question sur le résultat." },
] as const;

export function OverviewPage(context: PageContext & { onNavigate: (page: string) => void }) {
  return (
    <div className="page-stack overview">
      <section className="page-intro overview-hero">
        <h1>Comprenez l’effet d’un changement de portefeuille.</h1>
        <p>
          Testez l’ajout d’un placement au portefeuille d’un profil fictif et
          comparez les résultats historiques.
        </p>
        <div className="hero-actions">
          <Button className="primary" type="button" onClick={() => context.onNavigate("simulation")}>
            <Play aria-hidden="true" />Commencer une simulation
          </Button>
          <Button type="button" onClick={() => context.onNavigate("profiles")}>
            <Users aria-hidden="true" />Voir les profils
          </Button>
        </div>
      </section>

      <section className="quick-start" aria-labelledby="quick-start-title">
        <h2 id="quick-start-title">Démarrage rapide</h2>
        <p className="help">Trois profils de démonstration, pas des personnes réelles.</p>
        <div className="quick-start-list">
          {context.personas.map(persona => (
            <button
              key={persona.id}
              type="button"
              className="quick-start-item"
              onClick={() => {
                context.onChoose(persona);
                context.onNavigate("simulation");
              }}
            >
              <span className={`avatar avatar-${persona.id}`} aria-hidden="true">{persona.name.charAt(0)}</span>
              <span className="quick-start-text">
                <strong>{persona.name}</strong>
                <span>{persona.objective}</span>
              </span>
              <ArrowRight aria-hidden="true" className="quick-start-arrow" />
            </button>
          ))}
        </div>
      </section>

      <section className="how-it-works" aria-label="Comment ça marche">
        {overviewSteps.map(({ page, icon: Icon, title, text }, index) => (
          <button key={page} type="button" className="how-step" onClick={() => context.onNavigate(page)}>
            <span className="how-icon" aria-hidden="true"><Icon /></span>
            <span>
              <strong>{index + 1}. {title}</strong>
              <span>{text}</span>
            </span>
          </button>
        ))}
      </section>
    </div>
  );
}

export function ProfilesPage(context: PageContext & { onNavigate: (page: string) => void }) {
  return (
    <div className="page-stack">
      <section className="page-intro compact">
        <h1>Explorer des objectifs différents</h1>
        <p className="help">Profils de démonstration : aucun revenu, capacité financière ni situation familiale.</p>
      </section>
      <div className="persona-grid profile-grid">
        {profileItems(context).map(({ persona, portfolio, scenario }) => (
          <ProfileCard
            key={persona.id}
            persona={persona}
            portfolio={portfolio}
            assets={context.assets}
            scenario={scenario}
            onChoose={() => {
              context.onChoose(persona);
              context.onNavigate("simulation");
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function SavedScenariosPage({
  saved,
  assets,
  onLoad,
  onRemove,
}: {
  saved: SavedScenario[];
  assets: Asset[];
  onLoad: (scenario: SavedScenario) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <Card className="saved-page">
      <p className="eyebrow">Sauvegardés sur cet appareil</p>
      <h1>Mes scénarios</h1>
      <p>Les scénarios sont conservés dans le navigateur de cet appareil, pas dans un compte ni sur le serveur.</p>
      {saved.length === 0 ? (
        <div className="empty">
          <h2>Aucun scénario enregistré</h2>
          <p>Après une simulation, enregistrez ses paramètres pour les retrouver ici.</p>
        </div>
      ) : (
        <div className="saved-list">
          {saved.map(item => {
            const personaId = item.request.persona_id;
            return (
              <article className="saved-item" key={item.id}>
                <div>
                  <h2>{personaId[0].toUpperCase() + personaId.slice(1)} · {positionLabel(item.request.symbol, assets)}</h2>
                  <p>{formatWeight(item.request.target_weight_pct)} · enregistré le {formatDate(item.saved_at.slice(0, 10))}</p>
                </div>
                <div className="saved-actions">
                  <Button type="button" onClick={() => onLoad(item)}>Rouvrir</Button>
                  <Button type="button" onClick={() => onRemove(item.id)}>Supprimer</Button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </Card>
  );
}

