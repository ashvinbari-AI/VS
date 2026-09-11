import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtNum } from "../utils/format";
import { COLOR_PRIMARY } from "../utils/theme";

export default function Narratives() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;
  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/narratives", {
      person_a: filters.personA, person_b: filters.personB, platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
    }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && !data.analysis_available && (
        <EmptyState
          title="Narrative analysis not run yet"
          message='Click "Run Analysis" (Data Sources page) to classify posts into narrative categories. This uses NLP -- either local rule-based classification or Gemini, if enabled in Settings.'
        />
      )}
      {data && data.analysis_available && (
        <div className="space-y-6">
          <div className="rounded-xl border border-silver/60 bg-white shadow-card overflow-x-auto">
            <div className="border-b border-silver/60 px-4 py-2 text-xs font-medium text-navy">{data.label}</div>
            <table className="w-full min-w-[700px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-dark/50">
                  <th className="px-3 py-2">Narrative</th>
                  <th className="px-3 py-2 text-right">{personAName} %</th>
                  <th className="px-3 py-2 text-right">{personBName} %</th>
                  <th className="px-3 py-2 text-right">{personAName} Avg Engagement</th>
                  <th className="px-3 py-2 text-right">{personBName} Avg Engagement</th>
                </tr>
              </thead>
              <tbody>
                {data.table.map((row: any) => (
                  <tr key={row.narrative} className="border-t border-silver/30">
                    <td className="px-3 py-2 font-medium">{row.narrative}</td>
                    <td className="px-3 py-2 text-right">{row.person_a_pct != null ? `${row.person_a_pct}%` : "N/A"}</td>
                    <td className="px-3 py-2 text-right">{row.person_b_pct != null ? `${row.person_b_pct}%` : "N/A"}</td>
                    <td className="px-3 py-2 text-right">{fmtNum(row.person_a_avg_engagement)}</td>
                    <td className="px-3 py-2 text-right">{fmtNum(row.person_b_avg_engagement)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ScatterCard title={`${personAName}: Volume × Engagement`} points={data.scatter.person_a} />
            <ScatterCard title={`${personBName}: Volume × Engagement`} points={data.scatter.person_b} />
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}

function ScatterCard({ title, points }: { title: string; points: any[] }) {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#E4E8F0" />
          <XAxis type="number" dataKey="content_volume" name="Volume" tick={{ fontSize: 11 }} />
          <YAxis type="number" dataKey="avg_engagement" name="Avg Engagement" tick={{ fontSize: 11 }} />
          <ZAxis type="number" dataKey="post_count" range={[60, 400]} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ payload }) => {
            if (!payload?.length) return null;
            const p = payload[0].payload;
            return (
              <div className="rounded-md border border-silver bg-white p-2 text-xs shadow">
                <div className="font-semibold">{p.narrative}</div>
                <div>Volume: {p.content_volume}</div>
                <div>Avg Engagement: {fmtNum(p.avg_engagement)}</div>
              </div>
            );
          }} />
          <Scatter data={points} fill={COLOR_PRIMARY} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
