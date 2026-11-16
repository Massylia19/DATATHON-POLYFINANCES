export type PersonaId = "amira" | "mateo" | "robert" | "alex";
export type ResultStatus = "success" | "partial" | "error";
export type CheckStatus = "consistent" | "tension" | "insufficient_information";

export interface Contradiction { id: string; title: string; message: string; }
export interface Persona { id: PersonaId; name: string; risk_level: string; horizon_years_min: number; horizon_years_max: number | null; objective: string; preferences: string[]; missing_information: string[]; contradictions?: Contradiction[]; }
export interface Position { symbol: string; weight_pct: number; }
export interface Portfolio { persona_id: PersonaId; positions: Position[]; construction_note?: string; }
export interface Scenario { persona_id: PersonaId; symbol: string; target_weight_pct: number; }
export interface Asset { ticker: string; name: string; asset_class: string; asset_class_label: string; sector: string; currency: string; }
export interface Bootstrap { personas: Persona[]; portfolios: Portfolio[]; scenarios: Scenario[]; assets: Asset[]; presentation: Record<string, unknown>; }
export interface ScenarioRequest { persona_id: PersonaId; symbol: string; target_weight_pct: number; }
export interface Metrics { total_return: number; annualized_volatility: number; max_drawdown: number; }
export interface PortfolioResult { weights_by_asset_pct: Record<string, number>; weights_by_class_pct: Record<string, number>; metrics: Metrics; }
export interface Analysis { persona: Persona; scenario: { added_symbol: string; target_weight_pct: number; funding_rule?: string }; period: { start: string; end: string; common_observations: number }; currency: string; before: PortfolioResult; after: PortfolioResult; delta_after_minus_before: { metrics: Metrics; weights_by_asset_pct: Record<string, number> }; series: { dates: string[]; before: number[]; after: number[] }; methodology: Record<string, unknown>; sources: Array<Record<string, unknown>>; limitations: string[]; }
export interface ProfileCheck { id: string; status: CheckStatus; title: string; message: string; evidence_refs: string[]; missing_information: string[]; }
export interface Explanation { summary: string; changes: Array<{ topic: string; message: string; evidence_refs: string[] }>; profile_assessment: Array<{ check_id: string; status: CheckStatus; message: string; evidence_refs: string[] }>; uncertainties: string[]; evidence_refs: string[]; tool_trace: Array<Record<string, unknown>>; }
export interface AnalysisResponse { status: Exclude<ResultStatus, "error">; analysis_id: string; request: ScenarioRequest; analysis: Analysis; checks: ProfileCheck[]; explanation: Explanation | null; warnings: string[]; tool_trace: Array<Record<string, unknown>>; presentation?: { summary?: string; metric_definitions?: Record<string, { title: string; definition: string }> }; }
export interface ApiError { code: string; message: string; }
export interface ComparisonResponse { status: "success" | "partial"; period: Analysis["period"]; variants: AnalysisResponse[]; warnings: string[]; }
export type InterpretResponse = { status: "ready"; request: ScenarioRequest } | { status: "clarification" | "unavailable"; message: string } | { status: "error"; error: ApiError };
export type FollowUpResponse = { status: "success"; answer: string; evidence_refs: string[]; origin: string } | { status: "error" | "unavailable"; message: string };
export interface PublicEvidence { label: string; value: string; source?: string; role?: string; date?: string; url?: string; limitation?: string; }
export interface EvidenceResponse { analysis_id: string; evidence: PublicEvidence[]; }
export interface SavedScenario { id: string; saved_at: string; request: ScenarioRequest; }
export interface CustomPortfolioRequest { persona_id: PersonaId; weights: Record<string, number>; }
export interface CustomPortfolioAnalysis { analysis_type: string; persona: Persona; scenario: { scenario_id: string; description: string; modification_type: string }; period: { start: string; end: string; common_observations: number }; currency: string; before: PortfolioResult; after: PortfolioResult; delta_after_minus_before: { metrics: Metrics; weights_by_asset_pct: Record<string, number> }; series: { dates: string[]; before: number[]; after: number[] }; methodology: Record<string, unknown>; sources: Array<Record<string, unknown>>; }
export type CustomPortfolioResponse = { status: "success"; } & CustomPortfolioAnalysis | { status: "error"; error: ApiError };
export interface ChatMessage { role: "user" | "assistant"; content: string; }
export interface ChatRequest { persona_id: PersonaId; question: string; analysis_id: string | null; history: ChatMessage[]; }
export interface ChatResponse { status: "success"; answer: string; persona_id: PersonaId; analysis_id: string | null; }
