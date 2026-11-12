import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { comparisonDeps, comparisonParams, useFilters } from "../state/FilterContext";
import { fmtNum } from "../utils/format";

export default function Narratives() {
  const { filters, selected, ready } = useFilters();
  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/narratives", comparisonParams(filters)),
    comparisonDeps(filters),
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
                  <th className="px-3 py-2" rowSpan={2}>Narrative</th>
                  {selected.map((p) => (
                    <th key={p.id} colSpan={2} className="border-l border-silver/30 px-3 pt-2 text-center normal-case">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
                        {p.name}
                      </span>
                    </th>
                  ))}
                </tr>
                <tr className="text-left text-[10px] uppercase text-dark/40">
                  {selected.map((p) => [
                    <th key={`${p.id}-pct`} className="border-l border-silver/30 px-3 pb-2 text-right">% of content</th>,
                    <th key={`${p.id}-eng`} className="px-3 pb-2 text-right">Avg Engagement</th>,
                  ])}
                </tr>
              </thead>
              <tbody>
                {data.table.map((row: any) => (
                  <tr key={row.narrative} className="border-t border-silver/30">
                    <td className="px-3 py-2 font-medium">{row.narrative}</td>
                    {selected.map((p) => {
                      const cell = row.people?.[p.id];
                      return [
                        <td key={`${p.id}-pct`} className="border-l border-silver/30 px-3 py-2 text-right">{cell?.pct != null ? `${cell.pct}%` : "N/A"}</td>,
                        <td key={`${p.id}-eng`} className="px-3 py-2 text-right">{fmtNum(cell?.avg_engagement)}</td>,
                      ];
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {selected.map((p) => (
              <ScatterCard key={p.id} title={`${p.name}: Volume × Engagement`} points={data.scatter[p.id] ?? []} color={p.color} />
            ))}
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}

function ScatterCard({ title, points, color }: { title: string; points: any[]; color: string }) {
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
          <Scatter data={points} fill={color} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
