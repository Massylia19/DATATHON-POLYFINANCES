import { BookOpen, Bookmark, ChevronRight, FlaskConical, Home, Menu, Moon, ShieldCheck, Sun, Users, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./lib/api";
import { scenarioKey } from "./lib/format";
import type {
  AnalysisResponse,
  Bootstrap,
  InterpretResponse,
  Persona,
  SavedScenario,
  ScenarioRequest,
} from "./types";
import { ScenarioPanel } from "./features/simulation/ScenarioPanel";
import { ChatWidget } from "./features/chat/ChatWidget";
import {
  CoherencePage,
  ComparisonPage,
  SourcesPage,
  SummaryPage,
} from "./features/simulation/ResultsWorkspace";
import {
  OverviewPage,
  ProfilesPage,
  SavedScenariosPage,
} from "./features/pages";

type PageId =
  | "overview"
  | "profiles"
  | "simulation"
  | "coherence"
  | "scenarios"
  | "sources";

const STORAGE_KEY = "alphaforge.scenarios.v1";
const NAV_ITEMS: Array<{ id: PageId; label: string; icon: LucideIcon; needsResult?: boolean }> = [
  { id: "overview", label: "Vue d’ensemble", icon: Home },
  { id: "profiles", label: "Profils fictifs", icon: Users },
  { id: "simulation", label: "Simuler un ajout", icon: FlaskConical },
  { id: "coherence", label: "Cohérence", icon: ShieldCheck, needsResult: true },
  { id: "scenarios", label: "Mes scénarios", icon: Bookmark },
  { id: "sources", label: "Sources et méthode", icon: BookOpen },
];

function isPageId(value: string): value is PageId {
  return NAV_ITEMS.some(item => item.id === value);
}

function initialPage(): PageId {
  const hash = window.location.hash.slice(1);
  return isPageId(hash) ? hash : "overview";
}

function loadSavedScenarios(): SavedScenario[] {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    const parsed: unknown = JSON.parse(stored);
    if (
      !parsed
      || typeof parsed !== "object"
      || !("version" in parsed)
      || parsed.version !== 1
      || !("items" in parsed)
      || !Array.isArray(parsed.items)
    ) return [];
    return parsed.items.filter((item): item is SavedScenario =>
      Boolean(
        item
        && typeof item === "object"
        && "id" in item && typeof item.id === "string"
        && "saved_at" in item && typeof item.saved_at === "string"
        && "request" in item
        && typeof item.request === "object"
        && item.request !== null
        && "persona_id" in item.request
        && "symbol" in item.request
        && "target_weight_pct" in item.request,
      ),
    );
  } catch {
    return [];
  }
}

function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [draft, setDraft] = useState<ScenarioRequest | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [formValid, setFormValid] = useState(true);
  const [error, setError] = useState("");
  const [interpretation, setInterpretation] = useState<InterpretResponse | null>(null);
  const [interpreting, setInterpreting] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [page, setPage] = useState<PageId>(initialPage);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>(loadSavedScenarios);
  const [storageError, setStorageError] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const requestNumber = useRef(0);
  const interpretationNumber = useRef(0);
  const draftRef = useRef<ScenarioRequest | null>(null);
  const analysisController = useRef<AbortController | null>(null);
  const interpretationController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.bootstrap(controller.signal).then(bootstrap => {
      if (controller.signal.aborted) return;
      setData(bootstrap);
      const first = bootstrap.scenarios[0];
      const initialDraft: ScenarioRequest = {
        persona_id: first.persona_id,
        symbol: first.symbol,
        target_weight_pct: first.target_weight_pct,
      };
      draftRef.current = initialDraft;
      setDraft(initialDraft);
    }).catch(reason => {
      if (controller.signal.aborted || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setError(reason instanceof Error ? reason.message : "Impossible de charger les données.");
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (!chatOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      const target = event.target as Element | null;
      if (target?.closest(".chat-window, .chat-launcher")) return;
      setChatOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [chatOpen]);

  useEffect(() => {
    const syncPage = () => {
      const hash = window.location.hash.slice(1);
      if (isPageId(hash)) setPage(hash);
    };
    window.addEventListener("popstate", syncPage);
    window.addEventListener("hashchange", syncPage);
    return () => {
      window.removeEventListener("popstate", syncPage);
      window.removeEventListener("hashchange", syncPage);
    };
  }, []);

  const navigate = useCallback((nextPage: string) => {
    if (!isPageId(nextPage)) return;
    setPage(nextPage);
    setMobileNavOpen(false);
    if (window.location.hash !== `#${nextPage}`) {
      window.history.pushState(null, "", `#${nextPage}`);
    }
  }, []);

  const invalidatePendingRequests = useCallback(() => {
    requestNumber.current += 1;
    interpretationNumber.current += 1;
    analysisController.current?.abort();
    interpretationController.current?.abort();
    setBusy(false);
    setInterpreting(false);
    setInterpretation(null);
  }, []);

  const updateDraft = useCallback((next: ScenarioRequest) => {
    if (!data) return;
    const portfolio = data.portfolios.find(item => item.persona_id === next.persona_id);
    const targetWeight = next.target_weight_pct;
    if (
      !portfolio
      || portfolio.positions.some(position => position.symbol === next.symbol)
      || !data.assets.some(asset => asset.ticker === next.symbol)
      || !Number.isFinite(targetWeight)
      || targetWeight < 1
      || targetWeight > 50
      || Math.abs((targetWeight - 1) * 2 - Math.round((targetWeight - 1) * 2)) > 1e-9
    ) return;
    invalidatePendingRequests();
    const normalized = { ...next, symbol: next.symbol.toUpperCase() };
    draftRef.current = normalized;
    setDraft(normalized);
  }, [data, invalidatePendingRequests]);

  const selectPersona = useCallback((personaId: Persona["id"]) => {
    if (!data) return;
    const scenario = data.scenarios.find(item => item.persona_id === personaId);
    const portfolio = data.portfolios.find(item => item.persona_id === personaId);
    if (!scenario || !portfolio) return;
    const available = data.assets.filter(
      asset => !portfolio.positions.some(position => position.symbol === asset.ticker),
    );
    const symbol = available.some(asset => asset.ticker === scenario.symbol)
      ? scenario.symbol
      : available[0]?.ticker;
    if (!symbol) {
      setError("Aucun placement admissible n’est disponible pour ce profil.");
      return;
    }
    updateDraft({
      persona_id: personaId,
      symbol,
      target_weight_pct: scenario.target_weight_pct,
    });
    setFormValid(true);
  }, [data, updateDraft]);

  const applyProposal = useCallback((proposal: ScenarioRequest) => {
    const portfolio = data?.portfolios.find(item => item.persona_id === proposal.persona_id);
    const valid =
      data
      && portfolio
      && data.assets.some(asset => asset.ticker === proposal.symbol)
      && !portfolio.positions.some(position => position.symbol === proposal.symbol)
      && Number.isFinite(proposal.target_weight_pct)
      && proposal.target_weight_pct >= 1
      && proposal.target_weight_pct <= 50
      && Math.abs((proposal.target_weight_pct - 1) * 2 - Math.round((proposal.target_weight_pct - 1) * 2)) < 1e-9;
    if (!valid) {
      setError("La proposition ne correspond pas à un scénario admissible. Vérifiez les paramètres.");
      return;
    }
    updateDraft(proposal);
    setFormValid(true);
    navigate("simulation");
  }, [data, navigate, updateDraft]);

  const onFormValidityChange = useCallback((valid: boolean) => {
    setFormValid(valid);
    if (!valid) invalidatePendingRequests();
  }, [invalidatePendingRequests]);

  const analyze = useCallback(async () => {
    const submitted = draftRef.current;
    if (!submitted || !formValid) return;
    const id = ++requestNumber.current;
    analysisController.current?.abort();
    const controller = new AbortController();
    analysisController.current = controller;
    const submittedKey = scenarioKey(submitted.persona_id, submitted.symbol, submitted.target_weight_pct);
    setBusy(true);
    setError("");
    try {
      const response = await api.analyze(submitted, controller.signal);
      const current = draftRef.current;
      if (
        id === requestNumber.current
        && current
        && scenarioKey(current.persona_id, current.symbol, current.target_weight_pct) === submittedKey
      ) {
        const responseKey = scenarioKey(
          response.request.persona_id,
          response.request.symbol,
          response.request.target_weight_pct,
        );
        if (responseKey !== submittedKey) {
          setError("Le service a retourné un résultat associé à d’autres paramètres. Relancez l’analyse.");
          return;
        }
        setResult(response);
      }
    } catch (reason) {
      if (id !== requestNumber.current || controller.signal.aborted) return;
      setError(reason instanceof Error ? reason.message : "L’analyse a échoué. Réessayez.");
    } finally {
      if (id === requestNumber.current) setBusy(false);
    }
  }, [formValid]);

  const interpret = useCallback(async (text: string) => {
    const submitted = draftRef.current;
    if (!submitted || interpreting) return;
    const id = ++interpretationNumber.current;
    const submittedKey = scenarioKey(submitted.persona_id, submitted.symbol, submitted.target_weight_pct);
    interpretationController.current?.abort();
    const controller = new AbortController();
    interpretationController.current = controller;
    setInterpreting(true);
    setInterpretation(null);
    setError("");
    try {
      const response = await api.interpret(text, submitted, controller.signal);
      const current = draftRef.current;
      if (
        id === interpretationNumber.current
        && current
        && scenarioKey(current.persona_id, current.symbol, current.target_weight_pct) === submittedKey
      ) setInterpretation(response);
    } catch (reason) {
      if (id !== interpretationNumber.current || controller.signal.aborted) return;
      setInterpretation({
        status: "unavailable",
        message: reason instanceof Error ? reason.message : "La demande n’a pas pu être comprise.",
      });
    } finally {
      if (id === interpretationNumber.current) setInterpreting(false);
    }
  }, [interpreting]);

  const persistScenarios = useCallback((items: SavedScenario[]) => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: 1, items }),
      );
      setStorageError("");
    } catch {
      setStorageError("Le navigateur n’a pas pu enregistrer les scénarios sur cet appareil.");
    }
  }, []);

  const saveScenario = useCallback((request: ScenarioRequest) => {
    const item: SavedScenario = {
      id: window.crypto.randomUUID(),
      saved_at: new Date().toISOString(),
      request: { ...request },
    };
    const next = [item, ...savedScenarios.filter(saved =>
      scenarioKey(saved.request.persona_id, saved.request.symbol, saved.request.target_weight_pct)
      !== scenarioKey(request.persona_id, request.symbol, request.target_weight_pct),
    )].slice(0, 50);
    setSavedScenarios(next);
    persistScenarios(next);
  }, [persistScenarios, savedScenarios]);

  const removeSavedScenario = useCallback((id: string) => {
    const next = savedScenarios.filter(item => item.id !== id);
    setSavedScenarios(next);
    persistScenarios(next);
  }, [persistScenarios, savedScenarios]);

  const loadSavedScenario = useCallback((item: SavedScenario) => {
    applyProposal(item.request);
  }, [applyProposal]);

  const portfolio = useMemo(
    () => data && draft
      ? data.portfolios.find(item => item.persona_id === draft.persona_id) ?? null
      : null,
    [data, draft],
  );
  const persona = data?.personas.find(item => item.id === draft?.persona_id);
  const stale = Boolean(
    !formValid
    || (result && draft && scenarioKey(result.request.persona_id, result.request.symbol, result.request.target_weight_pct)
      !== scenarioKey(draft.persona_id, draft.symbol, draft.target_weight_pct)),
  );

  if (error && !data) {
    return <main className="fatal"><h1>AlphaForge</h1><p>{error}</p><button onClick={() => location.reload()}>Réessayer</button></main>;
  }
  if (!data || !draft || !portfolio || !persona) {
    return <main className="loading" aria-live="polite">Chargement d’AlphaForge…</main>;
  }

  const pageTitle = NAV_ITEMS.find(item => item.id === page)?.label ?? "Vue d’ensemble";
  const scenarioStatus = busy ? "busy" : result && !stale ? "done" : result ? "changed" : "todo";
  const scenarioStatusLabel = {
    busy: "En cours…",
    done: "Analysé",
    changed: "À relancer",
    todo: "Non analysé",
  }[scenarioStatus];
  const pageContext = {
    personas: data.personas,
    portfolios: data.portfolios,
    scenarios: data.scenarios,
    assets: data.assets,
    onChoose: (selected: Persona) => selectPersona(selected.id),
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          className="mobile-menu"
          type="button"
          aria-label={mobileNavOpen ? "Fermer le menu" : "Ouvrir le menu"}
          aria-expanded={mobileNavOpen}
          onClick={() => setMobileNavOpen(open => !open)}
        >
          {mobileNavOpen ? <X /> : <Menu />}
        </button>
        <a className="brand" href="#overview" onClick={event => { event.preventDefault(); navigate("overview"); }}>
          <span className="mark" aria-hidden="true">▰</span>
          <span>AlphaForge</span>
          <span className="brand-tag">Simulation fictive</span>
        </a>
        <div className="header-actions">
          <button
            className="theme"
            aria-label={`Activer le thème ${theme === "dark" ? "clair" : "sombre"}`}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun /> : <Moon />}
          </button>
        </div>
      </header>

      <div className="app-frame">
        <aside className={`sidebar ${mobileNavOpen ? "open" : ""}`}>
          <nav aria-label="Navigation principale">
            {NAV_ITEMS.map(item => {
              const Icon = item.icon;
              const waiting = item.needsResult && scenarioStatus !== "done";
              return (
                <button
                  type="button"
                  key={item.id}
                  className={[page === item.id ? "active" : "", waiting ? "waiting" : ""].join(" ").trim()}
                  aria-current={page === item.id ? "page" : undefined}
                  aria-describedby={waiting ? "nav-needs-result" : undefined}
                  onClick={() => navigate(item.id)}
                >
                  <Icon aria-hidden="true" className="nav-icon" />
                  <span className="nav-label">{item.label}</span>
                  {item.needsResult && (
                    <span className={`nav-dot dot-${scenarioStatus}`} aria-hidden="true" />
                  )}
                </button>
              );
            })}
            <span id="nav-needs-result" className="sr-only">Disponible après une analyse à jour.</span>
          </nav>
          <button
            type="button"
            className={`sidebar-context status-${scenarioStatus}`}
            onClick={() => navigate("simulation")}
            aria-label={`Scénario en cours : ${persona.name}, ${draft.symbol} à ${draft.target_weight_pct} %. ${scenarioStatusLabel}. Ouvrir la simulation`}
          >
            <span className={`avatar avatar-${persona.id}`} aria-hidden="true">{persona.name.charAt(0)}</span>
            <span className="sidebar-context-text">
              <strong>{persona.name}</strong>
              <span>{draft.symbol} · {draft.target_weight_pct} %</span>
              <span className="scenario-status" aria-live="polite">
                {scenarioStatus === "busy" ? <span className="spinner" aria-hidden="true" /> : <i aria-hidden="true" />}
                {scenarioStatusLabel}
              </span>
            </span>
            <ChevronRight aria-hidden="true" className="sidebar-context-arrow" />
          </button>
        </aside>

        <main className="main-content">
          <div className="page-heading">
            <h1>{pageTitle}</h1>
          </div>
          {error && (
            <div className="error global" role="alert">
              {error}
              <button type="button" onClick={() => setError("")}>Fermer</button>
            </div>
          )}
          {storageError && <p className="notice" role="status">{storageError}</p>}

          {page === "overview" && (
            <OverviewPage {...pageContext} onNavigate={navigate} onOpenChat={() => setChatOpen(true)} />
          )}
          {page === "profiles" && (
            <ProfilesPage {...pageContext} onNavigate={navigate} />
          )}
          {page === "simulation" && (
            <div className="simulation-layout">
              <ScenarioPanel
                personas={data.personas}
                portfolio={portfolio}
                assets={data.assets}
                draft={draft}
                busy={busy}
                interpreting={interpreting}
                interpretation={interpretation}
                formValid={formValid}
                onValidityChange={onFormValidityChange}
                onDraft={updateDraft}
                onSelectPersona={selectPersona}
                onAnalyze={() => void analyze()}
                onInterpret={text => void interpret(text)}
                onApplyProposal={applyProposal}
              />
              <div className="simulation-results">
                {busy && <p className="loading-inline" aria-live="polite">Calcul des résultats et préparation de l’explication…</p>}
                <SummaryPage
                  result={result}
                  stale={stale}
                  assets={data.assets}
                  onNavigate={navigate}
                  onSave={saveScenario}
                  onAskQuestion={() => setChatOpen(true)}
                  comparison={<ComparisonPage draft={draft} personaName={persona.name} invalid={!formValid} assets={data.assets} />}
                />
              </div>
            </div>
          )}
          {page === "coherence" && (
            <CoherencePage result={result} stale={stale} persona={persona.name} onNavigate={navigate} />
          )}
          {page === "scenarios" && (
            <SavedScenariosPage
              saved={savedScenarios}
              assets={data.assets}
              onLoad={loadSavedScenario}
              onRemove={removeSavedScenario}
              onNavigate={navigate}
            />
          )}
          {page === "sources" && <SourcesPage result={result} stale={stale} />}
          <footer className="legal-footer">Simulation pédagogique · aucune transaction réelle · le passé ne prédit pas l’avenir.</footer>
        </main>
      </div>
      <ChatWidget
        persona={persona}
        analysisId={!stale ? result?.analysis_id ?? null : null}
        analysisLabel={!stale && result ? `${result.request.symbol} · ${result.request.target_weight_pct} %` : undefined}
        stale={Boolean(stale && result)}
        open={chatOpen}
        onOpenChange={setChatOpen}
      />
    </div>
  );
}

export default App;
