const pct = new Intl.NumberFormat("fr-CA", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const weight = new Intl.NumberFormat("fr-CA", { minimumFractionDigits: 0, maximumFractionDigits: 1 });
export const formatRatio = (value: number) => pct.format(value);
export const formatWeight = (value: number) => `${weight.format(value)} %`;
export const formatDate = (value: string) => new Intl.DateTimeFormat("fr-CA", { day: "numeric", month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00`));
export const scenarioKey = (persona_id: string, symbol: string, target_weight_pct: number) => `${persona_id}|${symbol}|${target_weight_pct}`;
