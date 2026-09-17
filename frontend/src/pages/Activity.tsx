import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CalendarDays, Clock3 } from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { KpiCompareCard } from "../components/KPI/KpiCompareCard";
import { ChartCard } from "../components/Charts/ChartCard";
import { ProofDrawer, type ProofRequest } from "../components/Proof/ProofDrawer";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtNum } from "../utils/format";
import { COLOR_GRID, COLOR_PRIMARY, COLOR_SECONDARY } from "../utils/theme";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function ActivityPage() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;
  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/activity", {
      person_a: filters.personA, person_b: filters.personB, platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
      period_days: filters.periodDays,
    }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom, filters.periodDays],
    ready
  );
  const [proof, setProof] = useState<ProofRequest | null>(null);

  if (!ready) return <SelectPeoplePrompt />;

  const openProof = (metric: string, label: string) => () =>
    setProof({
      personAId: filters.personA, personAName, personBId: filters.personB, personBName,
      metric, label, platform: filters.platform, contentType: filters.contentType,
      dateFrom: filters.dateFrom ?? undefined, periodDays: filters.periodDays,
    });

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="space-y-6">
          <ProofDrawer request={proof} onClose={() => setProof(null)} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCompareCard label="Posts / Day" valueA={fmtNum(data.person_a.posts_per_day, 2)} valueB={fmtNum(data.person_b.posts_per_day, 2)} labelA={personAName} labelB={personBName} onProof={openProof("posts_per_day", "Posts / Day")} />
            <KpiCompareCard label="Posts / Week" valueA={fmtNum(data.person_a.posts_per_week, 1)} valueB={fmtNum(data.person_b.posts_per_week, 1)} labelA={personAName} labelB={personBName} onProof={openProof("posts_per_week", "Posts / Week")} />
            <KpiCompareCard label="Active Days" valueA={fmtNum(data.person_a.active_days)} valueB={fmtNum(data.person_b.active_days)} labelA={personAName} labelB={personBName} onProof={openProof("active_days", "Active Days")} />
            <KpiCompareCard label="Longest Inactive (days)" valueA={fmtNum(data.person_a.longest_inactive_period_days, 1)} valueB={fmtNum(data.person_b.longest_inactive_period_days, 1)} labelA={personAName} labelB={personBName} onProof={openProof("longest_inactive_period_days", "Longest Inactive (days)")} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ChartCard title="Day-of-Week Distribution" icon={CalendarDays}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={DAYS.map((d) => ({ day: d.slice(0, 3), person_a: data.person_a.activity_by_day[d] ?? 0, person_b: data.person_b.activity_by_day[d] ?? 0 }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="person_a" name={personAName} fill={COLOR_PRIMARY} radius={[4, 4, 0, 0]} animationDuration={500} />
                  <Bar dataKey="person_b" name={personBName} fill={COLOR_SECONDARY} radius={[4, 4, 0, 0]} animationDuration={500} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Hourly Posting Distribution" icon={Clock3}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={Array.from({ length: 24 }, (_, h) => ({ hour: h, person_a: data.person_a.activity_by_hour[h] ?? 0, person_b: data.person_b.activity_by_hour[h] ?? 0 }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 10, fill: "#8B93A7" }} interval={1} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="person_a" name={personAName} fill={COLOR_PRIMARY} radius={[4, 4, 0, 0]} animationDuration={500} />
                  <Bar dataKey="person_b" name={personBName} fill={COLOR_SECONDARY} radius={[4, 4, 0, 0]} animationDuration={500} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}
