import type { Asset, Persona, Position } from "../types";
import { formatWeight } from "./format";

export const riskLabels: Record<string, string> = {
  high: "Risque élevé déclaré",
  moderate: "Risque modéré déclaré",
  low_to_moderate: "Risque faible à modéré déclaré",
};

const preferenceLabels: Record<string, string> = {
  AI: "intelligence artificielle",
  IA: "intelligence artificielle",
  technologies: "technologies émergentes",
  crypto: "cryptoactifs",
  diversification: "diversification",
  ESG: "critères environnementaux, sociaux et de gouvernance",
  stabilité: "stabilité",
  "peu de spéculation": "peu de placements spéculatifs",
  "entreprises établies": "entreprises établies",
  "peu de crypto": "peu de cryptoactifs",
};

export const missingInformationLabels: Record<string, string> = {
  loss_absorption_capacity: "la capacité à absorber une perte",
  liquidity_needs: "les besoins de liquidités à court terme",
  planned_withdrawals: "les retraits prévus",
  etf_holdings: "la composition détaillée des fonds du portefeuille",
  asset_specific_esg_evidence: "des preuves ESG propres à l’actif",
  independent_esg_assessment: "une évaluation ESG indépendante",
  sector_exposures: "la répartition réelle des placements par secteur",
};

export const checkStatusLabels = {
  consistent: "Aucune tension supplémentaire observée sur ce point",
  tension: "Point de vigilance",
  insufficient_information: "Informations insuffisantes",
} as const;

export function formatRisk(persona: Persona): string {
  return riskLabels[persona.risk_level] ?? "Niveau de risque déclaré";
}

export function formatPreferences(preferences: string[]): string {
  return preferences.map(value => preferenceLabels[value] ?? value).join(", ");
}

export function formatMissingInformation(items: string[]): string[] {
  return Array.from(new Set(items.map(item => missingInformationLabels[item] ?? "une information complémentaire à vérifier")));
}

export function positionLabel(symbol: string, assets: Asset[]): string {
  const asset = assets.find(item => item.ticker === symbol);
  return asset ? `${asset.name} — ${asset.ticker}` : symbol;
}

export function previewAllocation(
  positions: Position[],
  addedSymbol: string,
  weightPct: number,
  assets: Asset[],
): Array<{ symbol: string; label: string; before: number; after: number }> {
  const scale = 1 - weightPct / 100;
  const result = positions.map(position => ({
    symbol: position.symbol,
    label: positionLabel(position.symbol, assets),
    before: position.weight_pct,
    after: position.weight_pct * scale,
  }));
  result.push({
    symbol: addedSymbol,
    label: positionLabel(addedSymbol, assets),
    before: 0,
    after: weightPct,
  });
  return result;
}

export function formatAllocationPreview(value: number): string {
  return formatWeight(value);
}
