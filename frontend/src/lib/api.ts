import type { AnalysisResponse, Bootstrap, ComparisonResponse, FollowUpResponse, InterpretResponse, ScenarioRequest } from "../types";

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiClientError extends Error { constructor(message: string, public readonly status: number, public readonly code?: string) { super(message); } }

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, signal, headers: { "Content-Type": "application/json", ...init?.headers } });
  const body = await response.json().catch(() => null) as { detail?: { message?: string; code?: string } } | null;
  if (!response.ok) throw new ApiClientError(body?.detail?.message ?? "Le service est temporairement indisponible.", response.status, body?.detail?.code);
  return body as T;
}

export const api = {
  bootstrap: (signal?: AbortSignal) => request<Bootstrap>("/api/bootstrap", undefined, signal),
  analyze: (payload: ScenarioRequest, signal?: AbortSignal) => request<AnalysisResponse>("/api/analyses", { method: "POST", body: JSON.stringify(payload) }, signal),
  compare: (payload: { persona_id: string; symbol: string; weight_a_pct: number; weight_b_pct: number }, signal?: AbortSignal) => request<ComparisonResponse>("/api/comparisons", { method: "POST", body: JSON.stringify(payload) }, signal),
  interpret: (text: string, current_request?: ScenarioRequest, signal?: AbortSignal) => request<InterpretResponse>("/api/interpret", { method: "POST", body: JSON.stringify({ text, current_request }) }, signal),
  followUp: (analysis_id: string, question: string, signal?: AbortSignal) => request<FollowUpResponse>("/api/follow-ups", { method: "POST", body: JSON.stringify({ analysis_id, question }) }, signal),
};
