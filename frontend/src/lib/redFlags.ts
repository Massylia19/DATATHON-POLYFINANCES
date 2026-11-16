import type { Contradiction } from "../types";

/** Identifiants des contrôles qui signalent une contradiction dans le profil. */
export const CONTRADICTION_IDS = new Set([
  "speculation_preference_conflict",
  "risk_objective_conflict",
]);

const plainMessages: Record<string, (name: string) => string> = {
  speculation_preference_conflict: () =>
    `Aime les cryptos, mais veut éviter la spéculation.`,
  risk_objective_conflict: () =>
    `Accepte beaucoup de risque, mais veut protéger son argent.`,
};

export function plainContradiction(item: Contradiction, name: string): string {
  return plainMessages[item.id]?.(name) ?? item.message;
}

/** Prénom seul, sans la mention entre parenthèses (« Alex (Démo…) » → « Alex »). */
export function shortName(name: string): string {
  return name.split(" (")[0].trim() || name;
}
