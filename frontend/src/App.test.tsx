import { StrictMode } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api } from "./lib/api";
import type {
  AnalysisResponse,
  Bootstrap,
  ComparisonResponse,
  InterpretResponse,
  ScenarioRequest,
} from "./types";

vi.mock("./lib/api", () => ({
  api: {
    bootstrap: vi.fn(),
    analyze: vi.fn(),
    compare: vi.fn(),
    interpret: vi.fn(),
    followUp: vi.fn(),
    evidence: vi.fn(),
  },
}));

const personas: Bootstrap["personas"] = [
  { id: "amira", name: "Amira", risk_level: "high", horizon_years_min: 15, horizon_years_max: null, objective: "Croissance à long terme", preferences: ["IA", "technologies", "crypto", "diversification"], missing_information: ["loss_absorption_capacity", "liquidity_needs", "planned_withdrawals"] },
  { id: "mateo", name: "Mateo", risk_level: "moderate", horizon_years_min: 8, horizon_years_max: 12, objective: "Croissance équilibrée", preferences: ["ESG", "stabilité", "peu de spéculation"], missing_information: ["loss_absorption_capacity", "liquidity_needs", "planned_withdrawals"] },
  { id: "robert", name: "Robert", risk_level: "low_to_moderate", horizon_years_min: 3, horizon_years_max: 5, objective: "Préservation du capital et croissance", preferences: ["entreprises établies", "stabilité", "peu de crypto"], missing_information: ["loss_absorption_capacity", "liquidity_needs", "planned_withdrawals"] },
];

const bootstrap: Bootstrap = {
  personas,
  portfolios: [
    { persona_id: "amira", positions: [{ symbol: "SPY", weight_pct: 40 }, { symbol: "QQQ", weight_pct: 30 }, { symbol: "SHOP.TO", weight_pct: 15 }, { symbol: "BTC-USD", weight_pct: 15 }] },
    { persona_id: "mateo", positions: [{ symbol: "ESGV", weight_pct: 40 }, { symbol: "XBB.TO", weight_pct: 30 }, { symbol: "FTS.TO", weight_pct: 15 }, { symbol: "GLD", weight_pct: 15 }] },
    { persona_id: "robert", positions: [{ symbol: "ZST.TO", weight_pct: 40 }, { symbol: "XBB.TO", weight_pct: 30 }, { symbol: "GLD", weight_pct: 15 }, { symbol: "XIU.TO", weight_pct: 15 }] },
  ],
  scenarios: [
    { persona_id: "amira", symbol: "NVDA", target_weight_pct: 10 },
    { persona_id: "mateo", symbol: "XOM", target_weight_pct: 10 },
    { persona_id: "robert", symbol: "TSLA", target_weight_pct: 5 },
  ],
  assets: [
    { ticker: "SPY", name: "SPDR S&P 500 ETF Trust", asset_class: "etf_equity", asset_class_label: "Fonds d’actions", sector: "Broad", currency: "USD" },
    { ticker: "QQQ", name: "Invesco QQQ Trust", asset_class: "etf_equity", asset_class_label: "Fonds d’actions", sector: "Technology", currency: "USD" },
    { ticker: "SHOP.TO", name: "Shopify", asset_class: "equity", asset_class_label: "Actions", sector: "Technology", currency: "CAD" },
    { ticker: "BTC-USD", name: "Bitcoin", asset_class: "crypto", asset_class_label: "Cryptoactifs", sector: "Crypto", currency: "USD" },
    { ticker: "NVDA", name: "NVIDIA", asset_class: "equity", asset_class_label: "Actions", sector: "Technology", currency: "USD" },
    { ticker: "ESGV", name: "Vanguard ESG U.S. Stock ETF", asset_class: "etf_equity", asset_class_label: "Fonds d’actions", sector: "Broad", currency: "USD" },
    { ticker: "XBB.TO", name: "iShares Core Canadian Universe Bond Index ETF", asset_class: "etf_bond", asset_class_label: "Fonds d’obligations", sector: "Fixed Income", currency: "CAD" },
    { ticker: "FTS.TO", name: "Fortis", asset_class: "equity", asset_class_label: "Actions", sector: "Utilities", currency: "CAD" },
    { ticker: "GLD", name: "SPDR Gold Shares", asset_class: "etf_commodity", asset_class_label: "Fonds de matières premières", sector: "Commodities", currency: "USD" },
    { ticker: "XOM", name: "Exxon Mobil", asset_class: "equity", asset_class_label: "Actions", sector: "Energy", currency: "USD" },
    { ticker: "ZST.TO", name: "BMO Ultra Short-Term Bond ETF", asset_class: "etf_bond", asset_class_label: "Fonds d’obligations", sector: "Fixed Income", currency: "CAD" },
    { ticker: "XIU.TO", name: "iShares S&P/TSX 60 Index ETF", asset_class: "etf_equity", asset_class_label: "Fonds d’actions", sector: "Broad", currency: "CAD" },
    { ticker: "TSLA", name: "Tesla", asset_class: "equity", asset_class_label: "Actions", sector: "Automotive", currency: "USD" },
  ],
  presentation: {},
};

function analysisResponse(
  request: ScenarioRequest = { persona_id: "amira", symbol: "NVDA", target_weight_pct: 10 },
): AnalysisResponse {
  const persona = personas.find(item => item.id === request.persona_id)!;
  const beforeMetrics = { total_return: 0.7367, annualized_volatility: 0.218, max_drawdown: -0.3864 };
  const afterMetrics = { total_return: 1.1862, annualized_volatility: 0.256, max_drawdown: -0.4004 };
  return {
    status: "partial",
    analysis_id: `analysis-${request.persona_id}-${request.symbol}-${request.target_weight_pct}`,
    request,
    analysis: {
      persona,
      scenario: { added_symbol: request.symbol, target_weight_pct: request.target_weight_pct },
      period: { start: "2021-11-12", end: "2026-11-12", common_observations: 1228 },
      currency: "CAD",
      before: { weights_by_asset_pct: { SPY: 40, QQQ: 30, "SHOP.TO": 15, "BTC-USD": 15 }, weights_by_class_pct: { equity: 85, crypto: 15 }, metrics: beforeMetrics },
      after: { weights_by_asset_pct: { SPY: 36, QQQ: 27, "SHOP.TO": 13.5, "BTC-USD": 13.5, [request.symbol]: request.target_weight_pct }, weights_by_class_pct: { equity: 85, crypto: 15 }, metrics: afterMetrics },
      delta_after_minus_before: { metrics: { total_return: 0.4495, annualized_volatility: 0.038, max_drawdown: -0.014 }, weights_by_asset_pct: {} },
      series: { dates: ["2021-11-12", "2022-01-01"], before: [100, 110], after: [100, 120] },
      methodology: { method: "buy_and_hold" },
      sources: [{ id: "src_prices_daily", source: "Yahoo Finance via yfinance", file: "prices_daily.csv", retrieved_on: "2026-11-13", source_url: "https://finance.yahoo.com" }],
      limitations: ["Les résultats historiques ne prédisent pas les résultats futurs."],
    },
    checks: [
      { id: "concentration", status: "insufficient_information", title: "Concentration des placements", message: "La part détenue par les fonds n’est pas connue.", evidence_refs: ["analysis.after.metrics.annualized_volatility"], missing_information: ["etf_holdings"] },
    ],
    explanation: null,
    warnings: ["Bedrock indisponible."],
    tool_trace: [],
    presentation: { summary: "Le portefeuille a davantage progressé, avec davantage de fluctuations. Ce compromis est à examiner au regard de l’objectif du profil." },
  };
}

function comparisonResponse(): ComparisonResponse {
  return {
    status: "partial",
    period: { start: "2021-11-12", end: "2026-11-12", common_observations: 1228 },
    variants: [analysisResponse({ persona_id: "amira", symbol: "NVDA", target_weight_pct: 5 }), analysisResponse({ persona_id: "amira", symbol: "NVDA", target_weight_pct: 20 })],
    warnings: [],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(res => { resolve = res; });
  return { promise, resolve };
}

function renderApp() {
  return render(<StrictMode><App /></StrictMode>);
}

async function openSimulation() {
  const navigation = await screen.findByRole("navigation", { name: "Navigation principale" });
  fireEvent.click(
    within(navigation).getByRole("button", { name: "Simuler un ajout" }),
  );
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  vi.mocked(api.bootstrap).mockResolvedValue(bootstrap);
  vi.mocked(api.analyze).mockImplementation(request => Promise.resolve(analysisResponse(request)));
  vi.mocked(api.compare).mockResolvedValue(comparisonResponse());
  vi.mocked(api.interpret).mockResolvedValue({ status: "clarification", message: "Précisez la demande." });
  vi.mocked(api.followUp).mockResolvedValue({ status: "success", answer: "Réponse fondée sur le scénario.", evidence_refs: [], origin: "bedrock" });
  vi.mocked(api.evidence).mockResolvedValue({ analysis_id: "analysis-amira-NVDA-10", evidence: [] });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("parcours React AlphaForge", () => {
  it("explique les profils fictifs et la navigation avant toute analyse", async () => {
    renderApp();
    expect(await screen.findByRole("heading", { name: "Comprenez l’effet d’un changement de portefeuille." })).toBeInTheDocument();
    expect(screen.queryAllByText(/capacité à absorber une perte/i)).toHaveLength(0);
    expect(api.analyze).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Profils fictifs" }));
    expect(await screen.findByRole("heading", { name: "Explorer des objectifs différents" })).toBeInTheDocument();
    expect(screen.getAllByText(/capacité à absorber une perte/i)).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Explorer le profil de Mateo" }));
    expect(await screen.findByText("Préférences :", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Croissance équilibrée")).toBeInTheDocument();
    expect(api.analyze).not.toHaveBeenCalled();
  });

  it("ne traite pas l’annulation de bootstrap StrictMode comme une erreur", async () => {
    renderApp();
    expect(await screen.findByRole("heading", { name: "Comprenez l’effet d’un changement de portefeuille." })).toBeInTheDocument();
    expect(screen.queryByText(/signal is aborted/i)).not.toBeInTheDocument();
  });

  it("ignore une analyse tardive après le changement de profil", async () => {
    const pending = deferred<AnalysisResponse>();
    vi.mocked(api.analyze)
      .mockImplementationOnce(request => Promise.resolve(analysisResponse(request)))
      .mockReturnValueOnce(pending.promise);
    renderApp();
    await openSimulation();
    await screen.findByRole("heading", { name: "Décrire un changement" });
    fireEvent.click(screen.getByRole("button", { name: "Analyser le scénario" }));
    await waitFor(() => expect(api.analyze).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Mateo" }));
    pending.resolve(analysisResponse());
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Mateo" })).toHaveAttribute("aria-pressed", "true");
    });
    expect(screen.queryByText(/Amira · NVIDIA/)).not.toBeInTheDocument();
  });

  it("applique une proposition explicite pour un autre profil sans la remplacer par son scénario par défaut", async () => {
    vi.mocked(api.interpret).mockResolvedValue({
      status: "ready",
      request: { persona_id: "mateo", symbol: "NVDA", target_weight_pct: 15 },
    });
    renderApp();
    await openSimulation();
    fireEvent.click(screen.getByText("Décrire une demande avec vos mots (facultatif)"));
    fireEvent.change(screen.getByLabelText("Votre demande"), {
      target: { value: "Pour Mateo, ajouter 15 % de NVIDIA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Comprendre la demande" }));
    expect(await screen.findByText(/Demande comprise/)).toHaveTextContent("Mateo");
    fireEvent.click(screen.getByRole("button", { name: "Appliquer au formulaire" }));
    expect(screen.getByRole("button", { name: "Mateo" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("spinbutton", { name: "Saisir la part du nouvel actif en pourcentage" })).toHaveValue(15);
    expect(screen.getByRole("combobox", { name: "Actif à ajouter" })).toHaveValue("NVIDIA — NVDA");
    expect(api.analyze).not.toHaveBeenCalled();
  });

  it("ignore une interprétation tardive après une modification du scénario", async () => {
    const pending = deferred<InterpretResponse>();
    vi.mocked(api.interpret).mockReturnValue(pending.promise);
    renderApp();
    await openSimulation();
    fireEvent.click(screen.getByText("Décrire une demande avec vos mots (facultatif)"));
    fireEvent.change(screen.getByLabelText("Votre demande"), {
      target: { value: "Pour Amira, tester 15 % de NVIDIA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Comprendre la demande" }));
    await waitFor(() => expect(api.interpret).toHaveBeenCalledTimes(1));
    const weight = screen.getByRole("spinbutton", { name: "Saisir la part du nouvel actif en pourcentage" });
    fireEvent.change(weight, { target: { value: "12.5" } });
    pending.resolve({
      status: "ready",
      request: { persona_id: "amira", symbol: "NVDA", target_weight_pct: 15 },
    });
    await waitFor(() => expect(weight).toHaveValue(12.5));
    expect(screen.queryByText(/Demande comprise/)).not.toBeInTheDocument();
    expect(api.analyze).not.toHaveBeenCalled();
  });

  it("valide une saisie numérique vide ou hors plage avant tout appel", async () => {
    renderApp();
    await openSimulation();
    const weight = await screen.findByRole("spinbutton", { name: "Saisir la part du nouvel actif en pourcentage" });
    fireEvent.change(weight, { target: { value: "50.5" } });
    expect(screen.getByRole("button", { name: "Analyser le scénario" })).toBeDisabled();
    fireEvent.change(weight, { target: { value: "" } });
    expect(screen.getByRole("button", { name: "Analyser le scénario" })).toBeDisabled();
    expect(api.analyze).not.toHaveBeenCalled();
  });

  it("n’affiche pas une comparaison tardive sous un autre poids de scénario", async () => {
    const pending = deferred<ComparisonResponse>();
    vi.mocked(api.compare).mockReturnValue(pending.promise);
    renderApp();
    await openSimulation();
    fireEvent.click(screen.getByRole("button", { name: "Comparer" }));
    await waitFor(() => expect(api.compare).toHaveBeenCalledTimes(1));
    const weight = screen.getByRole("spinbutton", { name: "Saisir la part du nouvel actif en pourcentage" });
    fireEvent.change(weight, { target: { value: "15" } });
    pending.resolve(comparisonResponse());
    await waitFor(() => expect(screen.getByText(/paramètres de la comparaison ont changé/i)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Comparer" })).toBeEnabled();
    expect(screen.queryByText("Variante A · 5 %")).not.toBeInTheDocument();
  });

  it("remplace la page Assistant par le chat flottant", async () => {
    renderApp();
    const navigation = await screen.findByRole("navigation", { name: "Navigation principale" });
    expect(within(navigation).queryByRole("button", { name: "Assistant" })).not.toBeInTheDocument();
    await openSimulation();
    fireEvent.click(screen.getByRole("button", { name: "Analyser le scénario" }));
    await waitFor(() => expect(api.analyze).toHaveBeenCalledTimes(1));
    fireEvent.click(await screen.findByRole("button", { name: /Poser une question sur ce résultat/ }));
    expect(await screen.findByRole("dialog", { name: "Assistant AlphaForge" })).toBeInTheDocument();
  });

  it("enregistre et rouvre un scénario uniquement sur cet appareil", async () => {
    renderApp();
    await openSimulation();
    fireEvent.click(screen.getByRole("button", { name: "Analyser le scénario" }));
    const saveButton = await screen.findByRole("button", { name: "Enregistrer sur cet appareil" });
    fireEvent.click(saveButton);
    fireEvent.click(screen.getByRole("button", { name: "Mes scénarios" }));
    expect(await screen.findByText(/Amira · NVIDIA/)).toBeInTheDocument();
    expect(screen.getByText(/dans le navigateur de cet appareil/i)).toBeInTheDocument();
    const savedItem = screen.getByText(/Amira · NVIDIA/).closest("article");
    expect(savedItem).not.toBeNull();
    fireEvent.click(within(savedItem as HTMLElement).getByRole("button", { name: "Rouvrir" }));
    expect(await screen.findByRole("heading", { name: "Simuler un ajout" })).toBeInTheDocument();
  }, 15_000);
});
