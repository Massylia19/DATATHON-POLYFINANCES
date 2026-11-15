import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Analysis } from "../types";
import { formatDate } from "../lib/format";

const formatIndex = (value: number) =>
  value.toLocaleString("fr-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const formatMonth = (value: string) =>
  new Intl.DateTimeFormat("fr-CA", { month: "short", year: "numeric" })
    .format(new Date(`${value}T00:00:00`));

export function HistoricalChart({ analysis }: { analysis: Analysis }) {
  const data = analysis.series.dates.map((date, index) => ({
    date,
    before: analysis.series.before[index],
    after: analysis.series.after[index],
  }));
  const sampleStep = Math.max(1, Math.floor(data.length / 20));
  const sampled = data.filter((_, index) =>
    index % sampleStep === 0 || index === data.length - 1,
  );
  return (
    <section className="chart-block">
      <h3>Évolution historique</h3>
      <p className="chart-note">Indice en base 100 au début de la période — ce n’est pas une valeur en dollars.</p>
      <div className="chart" role="img" aria-label="Courbes historiques indexées en base 100, portefeuille initial en trait pointillé et portefeuille après l’ajout en trait continu">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: -10 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              minTickGap={55}
              tickFormatter={(value: string) => formatMonth(value)}
              stroke="var(--muted)"
            />
            <YAxis
              stroke="var(--muted)"
              tickFormatter={(value: number) => value.toLocaleString("fr-CA", { maximumFractionDigits: 0 })}
              width={42}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                borderColor: "var(--border)",
                borderRadius: 10,
                color: "var(--text)",
              }}
              labelFormatter={value => formatDate(String(value))}
              formatter={(value, name) => [
                formatIndex(Number(value)),
                String(name),
              ]}
            />
            <Line
              type="linear"
              dataKey="before"
              name="Portefeuille de départ"
              stroke="var(--line-before)"
              strokeDasharray="6 4"
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
            />
            <Line
              type="linear"
              dataKey="after"
              name="Après l’ajout"
              stroke="var(--accent)"
              dot={false}
              strokeWidth={2.5}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="legend" aria-label="Légende du graphique">
        <span><i className="line before" />Portefeuille de départ — trait pointillé</span>
        <span><i className="line after" />Après l’ajout — trait continu</span>
      </div>
      <details>
        <summary>Voir un tableau échantillonné des valeurs (base 100)</summary>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Date</th><th>Portefeuille de départ</th><th>Après l’ajout</th></tr></thead>
            <tbody>
              {sampled.map(row => (
                <tr key={row.date}>
                  <td>{formatDate(row.date)}</td>
                  <td>{formatIndex(row.before)}</td>
                  <td>{formatIndex(row.after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
