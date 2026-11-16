import type { AnalysisResponse, Bootstrap, ComparisonResponse, CustomPortfolioRequest, CustomPortfolioResponse, ChatRequest, ChatResponse, EvidenceResponse, FollowUpResponse, InterpretResponse, ScenarioRequest } from "../types";

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const DEFAULT_TIMEOUT_MS = 60_000;
const AGENT_TIMEOUT_MS = 180_000;
const COMPARISON_TIMEOUT_MS = 360_000;

export class ApiClientError extends Error { constructor(message: string, public readonly status: number, public readonly code?: string) { super(message); } }

async function request<T>(
  path: string,
  init?: RequestInit,
  signal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const abortRequest = () => controller.abort();
  signal?.addEventListener("abort", abortRequest, { once: true });
  if (signal?.aborted) controller.abort();

  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal, headers: { "Content-Type": "application/json", ...init?.headers } });
    const body = await response.json().catch(() => null) as { detail?: { message?: string; code?: string } | Array<{ loc?: Array<string | number>; msg?: string }> } | null;
    if (!response.ok) {
      const detail = body?.detail;
      const validationMessage = Array.isArray(detail)
        ? detail.map(item => `${item.loc?.slice(1).join(".") ?? "requête"} : ${item.msg ?? "valeur invalide"}`).join("; ")
        : undefined;
      throw new ApiClientError(
        validationMessage ?? (!Array.isArray(detail) ? detail?.message : undefined) ?? "Le service est temporairement indisponible.",
        response.status,
        !Array.isArray(detail) ? detail?.code : undefined,
      );
    }
    return body as T;
  } catch (reason) {
    if (reason instanceof ApiClientError) throw reason;
    if (timedOut) throw new ApiClientError("Le service met trop de temps à répondre. Réessayez.", 408, "REQUEST_TIMEOUT");
    if (signal?.aborted) throw reason;
    throw new ApiClientError("Impossible de joindre le service AlphaForge. Vérifiez que l’API est lancée.", 0, "NETWORK_ERROR");
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortRequest);
  }
}

export const api = {
  bootstrap: (signal?: AbortSignal) => request<Bootstrap>("/api/bootstrap", undefined, signal),
  analyze: (payload: ScenarioRequest, signal?: AbortSignal) => request<AnalysisResponse>("/api/analyses", { method: "POST", body: JSON.stringify(payload) }, signal, AGENT_TIMEOUT_MS),
  compare: (payload: { persona_id: string; symbol: string; weight_a_pct: number; weight_b_pct: number }, signal?: AbortSignal) => request<ComparisonResponse>("/api/comparisons", { method: "POST", body: JSON.stringify(payload) }, signal, COMPARISON_TIMEOUT_MS),
  analyzeCustomPortfolio: (payload: CustomPortfolioRequest, signal?: AbortSignal) => request<CustomPortfolioResponse>("/api/custom-portfolio", { method: "POST", body: JSON.stringify(payload) }, signal, AGENT_TIMEOUT_MS),
  interpret: (text: string, current_request?: ScenarioRequest, signal?: AbortSignal) => request<InterpretResponse>("/api/interpret", { method: "POST", body: JSON.stringify({ text, current_request }) }, signal, AGENT_TIMEOUT_MS),
  followUp: (analysis_id: string, question: string, signal?: AbortSignal) => request<FollowUpResponse>("/api/follow-ups", { method: "POST", body: JSON.stringify({ analysis_id, question }) }, signal, AGENT_TIMEOUT_MS),
  evidence: (analysis_id: string, references: string[], signal?: AbortSignal) => request<EvidenceResponse>("/api/evidence", { method: "POST", body: JSON.stringify({ analysis_id, references }) }, signal),
  chat: (payload: ChatRequest, signal?: AbortSignal) => request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify(payload) }, signal, AGENT_TIMEOUT_MS),
};
