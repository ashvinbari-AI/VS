import {
  PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip,
} from "recharts";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtNum, fmtPct } from "../utils/format";
import { COLOR_PRIMARY, COLOR_SECONDARY } from "../utils/theme";

/** Engagement rate is a percentage with meaningful sub-1 precision (e.g.
 * 0.4489%) -- fmtNum's default 0-decimal rounding would show it as "0". */
function fmtMetric(key: string, value: unknown): string {
  if (typeof value !== "number") return "N/A";
  if (key === "engagement_rate") return fmtPct(value, 2);
  return fmtNum(value, Number.isInteger(value) ? 0 : 2);
}

interface ComparisonResponse {
  person_a: Record<string, any>;
  person_b: Record<string, any>;
  comparisons: Record<string, { label: string; direction: string; person_a: any; person_b: any; winner: string | null }>;
  narrative_diversity: { person_a: any; person_b: any };
  activity_consistency: { person_a: any; person_b: any };
  normalized_analytics_index: { note: string; dimensions: Record<string, { person_a: number | null; person_b: number | null }> };
}

export default function Comparison() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;

  const { data, loading, error, reload } = useApi<ComparisonResponse>(
    () =>
      api.get("/comparison", {
        person_a: filters.personA, person_b: filters.personB,
        platform: filters.platform, content_type: filters.contentType,
        date_from: filters.dateFrom, date_to: filters.dateTo, period_days: filters.periodDays,
      }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom, filters.periodDays],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && (
        <ComparisonBody
          data={data}
          personAId={filters.personA}
          personBId={filters.personB}
          nameA={personAName}
          nameB={personBName}
        />
      )}
    </AsyncBoundary>
  );
}

function ComparisonBody({
  data, personAId, personBId, nameA, nameB,
}: { data: ComparisonResponse; personAId: string; personBId: string; nameA: string; nameB: string }) {
  // Keep dataKeys stable (person_a/person_b) and only use the real names for
  // display (name prop) -- avoids collapsing both series if nameA === nameB
  // (e.g. before two distinct people are picked).
  const radarData = Object.entries(data.normalized_analytics_index.dimensions).map(([dim, v]) => ({
    dimension: dim, person_a: v.person_a ?? 0, person_b: v.person_b ?? 0,
  }));

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-silver/60 bg-white shadow-card overflow-x-auto">
        <table className="w-full min-w-[700px] text-sm">
          <thead>
            <tr className="border-b border-silver/60 bg-silver/10 text-left text-xs font-semibold uppercase tracking-wide text-dark/60">
              <th className="px-3 py-2">Metric</th>
              <th className="px-3 py-2 text-right">{nameA}</th>
              <th className="px-3 py-2 text-right">{nameB}</th>
              <th className="px-3 py-2 text-right">Difference</th>
              <th className="px-3 py-2 text-center">Winner</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.comparisons).map(([key, m]) => {
              const diff = typeof m.person_a === "number" && typeof m.person_b === "number"
                ? m.person_a - m.person_b : null;
              return (
                <tr key={key} className="border-b border-silver/30 last:border-0">
                  <td className="px-3 py-2 font-medium text-dark">{m.label}</td>
                  <td className="px-3 py-2 text-right">{fmtMetric(key, m.person_a)}</td>
                  <td className="px-3 py-2 text-right">{fmtMetric(key, m.person_b)}</td>
                  <td className="px-3 py-2 text-right text-dark/60">{diff === null ? "N/A" : fmtMetric(key, diff)}</td>
                  <td className="px-3 py-2 text-center">
                    {m.direction === "neutral" ? (
                      <span className="text-xs text-dark/40">— not applicable —</span>
                    ) : m.winner ? (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${m.winner === personAId ? "bg-navy/10 text-navy" : "bg-gold/20 text-dark"}`}>
                        {m.winner === personAId ? nameA : nameB}
                      </span>
                    ) : (
                      <span className="text-xs text-dark/40">Tie / N/A</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
          <h3 className="text-sm font-semibold text-dark">Normalized Analytics Index</h3>
          <p className="mt-1 text-xs text-dark/50">{data.normalized_analytics_index.note}</p>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} outerRadius={90}>
              <PolarGrid stroke="#E4E8F0" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Radar name={nameA} dataKey="person_a" stroke={COLOR_PRIMARY} fill={COLOR_PRIMARY} fillOpacity={0.25} />
              <Radar name={nameB} dataKey="person_b" stroke={COLOR_SECONDARY} fill={COLOR_SECONDARY} fillOpacity={0.35} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-4">
          <DiversityCard title="Narrative Diversity" a={data.narrative_diversity.person_a} b={data.narrative_diversity.person_b} nameA={nameA} nameB={nameB} />
          <ConsistencyCard title="Activity Consistency" a={data.activity_consistency.person_a} b={data.activity_consistency.person_b} nameA={nameA} nameB={nameB} />
        </div>
      </div>
    </div>
  );
}

function DiversityCard({
  title, a, b, nameA, nameB,
}: { title: string; a: any; b: any; nameA: string; nameB: string }) {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      {!a && !b ? (
        <p className="text-xs text-dark/40">Run analysis (NLP pass) to compute narrative diversity.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Stat label={`Unique Narratives (${nameA})`} value={fmtNum(a?.unique_narratives)} />
          <Stat label={`Unique Narratives (${nameB})`} value={fmtNum(b?.unique_narratives)} />
          <Stat label={`Dominant % (${nameA})`} value={a?.dominant_pct != null ? `${a.dominant_pct}%` : "N/A"} />
          <Stat label={`Dominant % (${nameB})`} value={b?.dominant_pct != null ? `${b.dominant_pct}%` : "N/A"} />
        </div>
      )}
    </div>
  );
}

function ConsistencyCard({
  title, a, b, nameA, nameB,
}: { title: string; a: any; b: any; nameA: string; nameB: string }) {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label={`Median Interval (${nameA}, hrs)`} value={fmtNum(a?.median_interval_hours, 1)} />
        <Stat label={`Median Interval (${nameB}, hrs)`} value={fmtNum(b?.median_interval_hours, 1)} />
        <Stat label={`Longest Gap (${nameA}, days)`} value={fmtNum(a?.longest_gap_days, 1)} />
        <Stat label={`Longest Gap (${nameB}, days)`} value={fmtNum(b?.longest_gap_days, 1)} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-dark/50">{label}</div>
      <div className="text-base font-semibold text-navy">{value}</div>
    </div>
  );
}
