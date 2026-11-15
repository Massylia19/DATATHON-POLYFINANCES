import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Analysis } from "../types";

export function HistoricalChart({ analysis }: { analysis: Analysis }) {
  const data = analysis.series.dates.map((date, index) => ({ date, before: analysis.series.before[index], after: analysis.series.after[index] }));
  return <section className="chart-block"><h3>Évolution historique</h3><div className="chart" role="img" aria-label="Courbes historiques des portefeuilles avant et après">
    <ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: -10 }}><CartesianGrid stroke="var(--border)" vertical={false} /><XAxis dataKey="date" minTickGap={55} tickFormatter={(v: string) => v.slice(0, 4)} stroke="var(--muted)" /><YAxis stroke="var(--muted)" /><Tooltip contentStyle={{ background: "var(--surface)", borderColor: "var(--border)", borderRadius: 10 }} labelFormatter={(v) => String(v)} /><Line type="monotone" dataKey="before" name="Portefeuille initial" stroke="#b6f5d0" dot={false} strokeWidth={2} /><Line type="monotone" dataKey="after" name="Après l’ajout" stroke="var(--accent)" dot={false} strokeWidth={2.5} /></LineChart></ResponsiveContainer>
  </div><div className="legend"><span><i className="line before" />Portefeuille initial</span><span><i className="line after" />Après l’ajout</span><span>Base 100</span></div>
  <details><summary>Voir les valeurs sous forme de tableau</summary><div className="table-scroll"><table><thead><tr><th>Date</th><th>Avant</th><th>Après</th></tr></thead><tbody>{data.filter((_, i) => i % Math.max(1, Math.floor(data.length / 20)) === 0 || i === data.length - 1).map(row => <tr key={row.date}><td>{row.date}</td><td>{row.before.toFixed(2)}</td><td>{row.after.toFixed(2)}</td></tr>)}</tbody></table></div></details></section>;
}
