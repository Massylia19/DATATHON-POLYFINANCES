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
  return (
    <Card className="persona-card">
      <p className="eyebrow">{formatRisk(persona)}</p>
      <h2>{persona.name}</h2>
      <p className="persona-objective">{persona.objective}</p>
      <p><b>Horizon :</b> {persona.horizon_years_min}{persona.horizon_years_max ? `–${persona.horizon_years_max} ans` : " ans et plus"}</p>
      <p><b>Préférences :</b> {formatPreferences(persona.preferences)}</p>
      <p className="demo-question">À explorer : {demoQuestions[persona.id]}</p>
      <details>
        <summary>Voir son portefeuille de départ</summary>
        <ul className="holding-list">
          {portfolio.positions.map(position => (
            <li key={position.symbol}>
              <span>{positionLabel(position.symbol, assets)}</span>
              <strong>{formatWeight(position.weight_pct)}</strong>
            </li>
          ))}
        </ul>
      </details>
      <p className="help">
        Exemple de départ : {scenario.symbol} à {formatWeight(scenario.target_weight_pct)}.
      </p>
      <Button className="primary" type="button" onClick={onChoose}>
        Explorer le profil de {persona.name}
      </Button>
      <p className="help">
        Informations non renseignées : {missing.join(" · ")}.
      </p>
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

export function OverviewPage(context: PageContext & { onNavigate: (page: string) => void }) {
  return (
    <div className="page-stack">
      <section className="page-intro">
        <p className="eyebrow">AlphaForge · simulation pédagogique</p>
        <h1>Comprenez l’effet d’un changement de portefeuille.</h1>
        <p>
          Choisissez une situation fictive, testez l’ajout d’un placement et
          explorez les résultats historiques ainsi que les points de vigilance.
        </p>
        <p className="notice">
          Amira, Mateo et Robert sont des profils de démonstration. Vous n’avez
          pas besoin de choisir une personne qui vous ressemble.
        </p>
        <Button className="primary" type="button" onClick={() => context.onNavigate("simulation")}>
          Commencer une simulation
        </Button>
      </section>
      <section>
        <div className="section-heading">
          <div><p className="eyebrow">Trois situations fictives</p><h2>Choisir un profil</h2></div>
          <Button type="button" onClick={() => context.onNavigate("profiles")}>Voir les profils</Button>
        </div>
        <div className="persona-grid">
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
      </section>
      <section className="feature-strip" aria-label="Parcours d’analyse">
        <article><span>01</span><h3>Simuler</h3><p>Modifier un ajout et observer les métriques calculées.</p></article>
        <article><span>02</span><h3>Examiner</h3><p>Lire les points de vigilance et les informations manquantes.</p></article>
        <article><span>03</span><h3>Comprendre</h3><p>Consulter les preuves et poser une question liée au résultat.</p></article>
      </section>
    </div>
  );
}

export function ProfilesPage(context: PageContext & { onNavigate: (page: string) => void }) {
  return (
    <div className="page-stack">
      <section className="page-intro compact">
        <p className="eyebrow">Profils fictifs</p>
        <h1>Explorer des objectifs différents</h1>
        <p>
          Les profils ne représentent pas des clients réels. Ils ne contiennent
          pas de revenu, de capacité financière ou de situation familiale.
        </p>
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

