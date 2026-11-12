import {
  Legend, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip,
} from "recharts";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { Section } from "../components/Layout/Section";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { comparisonDeps, comparisonParams, useFilters, type SelectedPerson } from "../state/FilterContext";
import { fmtNum, fmtPct } from "../utils/format";

/** Engagement rate is a percentage with meaningful sub-1 precision (e.g.
 * 0.4489%) -- fmtNum's default 0-decimal rounding would show it as "0". */
function fmtMetric(key: string, value: unknown): string {
  if (typeof value !== "number") return "N/A";
  if (key === "engagement_rate") return fmtPct(value, 2);
  return fmtNum(value, Number.isInteger(value) ? 0 : 2);
}

type PerPerson<T> = Record<string, T>;

interface ComparisonResponse {
  person_ids: string[];
  people: PerPerson<Record<string, any>>;
  comparisons: Record<string, {
    label: string; direction: string; values: PerPerson<any>; winner: string | null; leader_margin: number | null;
  }>;
  narrative_diversity: PerPerson<any>;
  activity_consistency: PerPerson<any>;
  normalized_analytics_index: { note: string; dimensions: Record<string, { values: PerPerson<number | null> }> };
}

export default function Comparison() {
  const { filters, selected, ready } = useFilters();

  const { data, loading, error, reload } = useApi<ComparisonResponse>(
    () => api.get("/comparison", { ...comparisonParams(filters), period_days: filters.periodDays }),
    [...comparisonDeps(filters), filters.periodDays],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && <ComparisonBody data={data} people={selected} />}
    </AsyncBoundary>
  );
}

function ComparisonBody({ data, people }: { data: ComparisonResponse; people: SelectedPerson[] }) {
  const byId = Object.fromEntries(people.map((p) => [p.id, p]));
  // dataKeys are person ids (stable even if two people share a display name).
  const radarData = Object.entries(data.normalized_analytics_index.dimensions).map(([dim, v]) => ({
    dimension: dim,
    ...Object.fromEntries(people.map((p) => [p.id, v.values?.[p.id] ?? 0])),
  }));
  const fillOpacity = people.length > 2 ? 0.12 : 0.3;

  return (
    <div className="space-y-8">
      <Section title="Metric by metric" description="The leader is only named when one person is clearly ahead and nobody's value is missing.">
      <div className="rounded-xl border border-silver/60 bg-white shadow-card overflow-x-auto">
        <table className="w-full min-w-[700px] text-sm">
          <thead>
            <tr className="border-b border-silver/60 bg-silver/10 text-left text-xs font-semibold uppercase tracking-wide text-dark/60">
              <th className="px-3 py-2">Metric</th>
              {people.map((p) => (
                <th key={p.id} className="px-3 py-2 text-right">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
                    {p.name}
                  </span>
                </th>
              ))}
              <th className="px-3 py-2 text-center">Leader</th>
              <th className="px-3 py-2 text-right" title="How far the leader is ahead of the next-closest person">Lead Margin</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.comparisons).map(([key, m]) => {
              const winner = m.winner ? byId[m.winner] : null;
              return (
                <tr key={key} className="border-b border-silver/30 last:border-0">
                  <td className="px-3 py-2 font-medium text-dark">{m.label}</td>
                  {people.map((p) => (
                    <td key={p.id} className={`px-3 py-2 text-right ${m.winner === p.id ? "font-semibold text-dark" : ""}`}>
                      {fmtMetric(key, m.values?.[p.id])}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-center">
                    {m.direction === "neutral" ? (
                      <span className="text-xs text-dark/40">— not applicable —</span>
                    ) : winner ? (
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-semibold text-dark"
                        style={{ backgroundColor: `${winner.color}26`, color: winner.color }}
                      >
                        {winner.name}
                      </span>
                    ) : (
                      <span className="text-xs text-dark/40">Tie / N/A</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right text-dark/60">
                    {m.leader_margin == null ? "N/A" : fmtMetric(key, m.leader_margin)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      </Section>

      <Section title="Profile shape" description="Overall strengths, content variety and posting rhythm.">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
          <h3 className="text-sm font-semibold text-dark">Normalized Analytics Index</h3>
          <p className="mt-1 text-xs text-dark/50">{data.normalized_analytics_index.note}</p>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData} outerRadius={90}>
              <PolarGrid stroke="#E4E8F0" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {people.map((p) => (
                <Radar key={p.id} name={p.name} dataKey={p.id} stroke={p.color} fill={p.color} fillOpacity={fillOpacity} />
              ))}
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-4">
          <PerPersonCard
            title="Narrative Diversity"
            people={people}
            emptyMessage={people.every((p) => !data.narrative_diversity[p.id]) ? "Run analysis (NLP pass) to compute narrative diversity." : undefined}
            columns={[
              { header: "Unique Narratives", value: (p) => fmtNum(data.narrative_diversity[p.id]?.unique_narratives) },
              { header: "Dominant %", value: (p) => {
                const v = data.narrative_diversity[p.id]?.dominant_pct;
                return v != null ? `${v}%` : "N/A";
              } },
            ]}
          />
          <PerPersonCard
            title="Activity Consistency"
            people={people}
            columns={[
              { header: "Median Interval (hrs)", value: (p) => fmtNum(data.activity_consistency[p.id]?.median_interval_hours, 1) },
              { header: "Longest Gap (days)", value: (p) => fmtNum(data.activity_consistency[p.id]?.longest_gap_days, 1) },
            ]}
          />
        </div>
      </div>
      </Section>
    </div>
  );
}

/** A small person-by-stat table: one row per selected person. */
function PerPersonCard({
  title, people, columns, emptyMessage,
}: {
  title: string;
  people: SelectedPerson[];
  columns: { header: string; value: (p: SelectedPerson) => string }[];
  emptyMessage?: string;
}) {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      {emptyMessage ? (
        <p className="text-xs text-dark/40">{emptyMessage}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] text-dark/50">
              <th className="py-1 font-medium">Person</th>
              {columns.map((c) => <th key={c.header} className="py-1 text-right font-medium">{c.header}</th>)}
            </tr>
          </thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.id} className="border-t border-silver/30">
                <td className="py-1.5">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
                    <span className="truncate">{p.name}</span>
                  </span>
                </td>
                {columns.map((c) => (
                  <td key={c.header} className="py-1.5 text-right font-semibold text-navy">{c.value(p)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
