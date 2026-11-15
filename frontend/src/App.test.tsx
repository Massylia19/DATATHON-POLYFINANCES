import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const bootstrap = {
  personas: [
    { id: "amira", name: "Amira", risk_level: "high", horizon_years_min: 15, horizon_years_max: null, objective: "Croissance", preferences: [], missing_information: [] },
    { id: "mateo", name: "Mateo", risk_level: "moderate", horizon_years_min: 8, horizon_years_max: 12, objective: "Équilibrée", preferences: [], missing_information: [] },
    { id: "robert", name: "Robert", risk_level: "low_to_moderate", horizon_years_min: 3, horizon_years_max: 5, objective: "Préservation", preferences: [], missing_information: [] },
  ],
  portfolios: ["amira", "mateo", "robert"].map(persona_id => ({ persona_id, positions: [{ symbol: persona_id === "amira" ? "SPY" : "GLD", weight_pct: 100 }] })),
  scenarios: [{ persona_id: "amira", symbol: "NVDA", target_weight_pct: 10 }, { persona_id: "mateo", symbol: "XOM", target_weight_pct: 10 }, { persona_id: "robert", symbol: "TSLA", target_weight_pct: 5 }],
  assets: [{ ticker: "NVDA", name: "NVIDIA", asset_class: "equity", asset_class_label: "Action", sector: "Technology", currency: "USD" }, { ticker: "XOM", name: "ExxonMobil", asset_class: "equity", asset_class_label: "Action", sector: "Energy", currency: "USD" }, { ticker: "TSLA", name: "Tesla", asset_class: "equity", asset_class_label: "Action", sector: "Automotive", currency: "USD" }], presentation: {},
};

afterEach(() => vi.restoreAllMocks());

describe("liaison du résultat au scénario", () => {
  it("n'affiche jamais une réponse lente sous un autre profil", async () => {
    let resolveAnalysis: ((value: Response) => void) | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/bootstrap")) return Promise.resolve(new Response(JSON.stringify(bootstrap), { status: 200 }));
      return new Promise<Response>(resolve => { resolveAnalysis = resolve; });
    }));
    render(<App />);
    await screen.findByText("Votre scénario");
    fireEvent.click(screen.getByRole("button", { name: "Analyser le scénario" }));
    fireEvent.click(screen.getByRole("button", { name: "Mateo" }));
    resolveAnalysis?.(new Response(JSON.stringify({ status: "partial", analysis_id: "id", request: { persona_id: "amira", symbol: "NVDA", target_weight_pct: 10 }, analysis: {}, checks: [], warnings: [], tool_trace: [] }), { status: 200 }));
    await waitFor(() => expect(screen.getByText("Vos résultats apparaîtront ici")).toBeInTheDocument());
    expect(screen.queryByText(/Amira · NVIDIA/)).not.toBeInTheDocument();
  });
});
