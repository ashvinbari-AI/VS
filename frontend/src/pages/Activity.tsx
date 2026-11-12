import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CalendarDays, Clock3 } from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { KpiCompareCard } from "../components/KPI/KpiCompareCard";
import { ChartCard } from "../components/Charts/ChartCard";
import { ProofDrawer, type ProofRequest } from "../components/Proof/ProofDrawer";
import { Section } from "../components/Layout/Section";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { comparisonDeps, comparisonParams, useFilters } from "../state/FilterContext";
import { fmtNum } from "../utils/format";
import { COLOR_GRID } from "../utils/theme";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function ActivityPage() {
  const { filters, selected, ready } = useFilters();
  const { data, loading, error, reload } = useApi<{ person_ids: string[]; people: Record<string, any> }>(
    () => api.get("/activity", { ...comparisonParams(filters), period_days: filters.periodDays }),
    [...comparisonDeps(filters), filters.periodDays],
    ready
  );
  const [proof, setProof] = useState<ProofRequest | null>(null);

  if (!ready) return <SelectPeoplePrompt />;

  const openProof = (metric: string, label: string) => () =>
    setProof({
      people: selected, metric, label, platform: filters.platform, contentType: filters.contentType,
      dateFrom: filters.dateFrom ?? undefined, periodDays: filters.periodDays,
    });

  const block = (id: string) => data?.people[id] ?? {};
  const kpi = (fmt: (b: any) => string) => selected.map((p) => ({ ...p, value: fmt(block(p.id)) }));

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="space-y-8">
          <ProofDrawer request={proof} onClose={() => setProof(null)} />
          <Section title="Posting rhythm" description="Click any card to see the posts behind it.">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCompareCard label="Posts / Day" values={kpi((b) => fmtNum(b.posts_per_day, 2))} onProof={openProof("posts_per_day", "Posts / Day")} />
            <KpiCompareCard label="Posts / Week" values={kpi((b) => fmtNum(b.posts_per_week, 1))} onProof={openProof("posts_per_week", "Posts / Week")} />
            <KpiCompareCard label="Active Days" values={kpi((b) => fmtNum(b.active_days))} onProof={openProof("active_days", "Active Days")} />
            <KpiCompareCard label="Longest Inactive (days)" values={kpi((b) => fmtNum(b.longest_inactive_period_days, 1))} onProof={openProof("longest_inactive_period_days", "Longest Inactive (days)")} />
          </div>
          </Section>

          <Section title="When they post" description="Posts by day of week and by hour of day.">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ChartCard title="Day-of-Week Distribution" icon={CalendarDays}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={DAYS.map((d) => ({
                  day: d.slice(0, 3),
                  ...Object.fromEntries(selected.map((p) => [p.id, block(p.id).activity_by_day?.[d] ?? 0])),
                }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {selected.map((p) => (
                    <Bar key={p.id} dataKey={p.id} name={p.name} fill={p.color} radius={[4, 4, 0, 0]} animationDuration={500} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Hourly Posting Distribution" icon={Clock3}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={Array.from({ length: 24 }, (_, h) => ({
                  hour: h,
                  ...Object.fromEntries(selected.map((p) => [p.id, block(p.id).activity_by_hour?.[h] ?? 0])),
                }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 10, fill: "#8B93A7" }} interval={1} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {selected.map((p) => (
                    <Bar key={p.id} dataKey={p.id} name={p.name} fill={p.color} radius={[4, 4, 0, 0]} animationDuration={500} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
          </Section>
        </div>
      )}
    </AsyncBoundary>
  );
}
