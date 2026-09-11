import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Users, FileText, Image, Clapperboard, Heart, MessageCircle, Percent, Flame, Trophy,
} from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { KpiCompareCard } from "../components/KPI/KpiCompareCard";
import { ChartCard } from "../components/Charts/ChartCard";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { DataTable } from "../components/Tables/DataTable";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtCompact, fmtDate, fmtNum, fmtPct } from "../utils/format";
import { COLOR_GRID, COLOR_PRIMARY, COLOR_SECONDARY } from "../utils/theme";

const COLOR_A = COLOR_PRIMARY;
const COLOR_B = COLOR_SECONDARY;

interface OverviewResponse {
  kpis: { person_a: any; person_b: any };
  charts: {
    content_activity_timeline: { date: string; person_a: number; person_b: number }[];
    engagement_timeline: { date: string; person_a: number | null; person_b: number | null }[];
    platform_distribution: { person_a: Record<string, number>; person_b: Record<string, number> };
    content_type_distribution: { person_a: Record<string, number>; person_b: Record<string, number> };
    engagement_comparison: { person_a: Record<string, number | null>; person_b: Record<string, number | null> };
    top_content: any[];
  };
}

export default function Overview() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;

  const { data, loading, error, reload } = useApi<OverviewResponse>(
    () =>
      api.get("/overview", {
        person_a: filters.personA, person_b: filters.personB,
        platform: filters.platform, content_type: filters.contentType,
        date_from: filters.dateFrom, date_to: filters.dateTo,
      }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && <OverviewBody data={data} nameA={personAName} nameB={personBName} />}
    </AsyncBoundary>
  );
}

function OverviewBody({ data, nameA, nameB }: { data: OverviewResponse; nameA: string; nameB: string }) {
  const a = data.kpis.person_a;
  const b = data.kpis.person_b;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCompareCard icon={Users} label="Followers" valueA={fmtCompact(a.followers)} valueB={fmtCompact(b.followers)} labelA={nameA} labelB={nameB} />
        <KpiCompareCard icon={FileText} label="Total Content" valueA={fmtNum(a.total_content)} valueB={fmtNum(b.total_content)} labelA={nameA} labelB={nameB} />
        <KpiCompareCard icon={Image} label="Posts" valueA={fmtNum(a.posts)} valueB={fmtNum(b.posts)} labelA={nameA} labelB={nameB} />
        <KpiCompareCard icon={Clapperboard} label="Reels" valueA={fmtNum(a.reels)} valueB={fmtNum(b.reels)} labelA={nameA} labelB={nameB} />
        <KpiCompareCard icon={Heart} label="Avg Likes" valueA={fmtCompact(a.average_likes)} valueB={fmtCompact(b.average_likes)} labelA={nameA} labelB={nameB} />
        <KpiCompareCard icon={MessageCircle} label="Avg Comments" valueA={fmtCompact(a.average_comments)} valueB={fmtCompact(b.average_comments)} labelA={nameA} labelB={nameB} />
        <KpiCompareCard icon={Percent} label="Engagement Rate" valueA={fmtPct(a.engagement_rate)} valueB={fmtPct(b.engagement_rate)} labelA={nameA} labelB={nameB} sublabel="engagement / followers" />
        <KpiCompareCard icon={Flame} label="Avg Engagement" valueA={fmtCompact(a.average_engagement)} valueB={fmtCompact(b.average_engagement)} labelA={nameA} labelB={nameB} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Content Activity Timeline">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.charts.content_activity_timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8B93A7" }} tickFormatter={(d) => fmtDate(d)} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
              <Tooltip labelFormatter={(d) => fmtDate(String(d))} contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="person_a" name={nameA} stroke={COLOR_A} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} animationDuration={500} />
              <Line type="monotone" dataKey="person_b" name={nameB} stroke={COLOR_B} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} animationDuration={500} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Engagement Timeline">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.charts.engagement_timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8B93A7" }} tickFormatter={(d) => fmtDate(d)} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={false} tickLine={false} />
              <Tooltip labelFormatter={(d) => fmtDate(String(d))} contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="person_a" name={nameA} stroke={COLOR_A} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} connectNulls animationDuration={500} />
              <Line type="monotone" dataKey="person_b" name={nameB} stroke={COLOR_B} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} connectNulls animationDuration={500} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Content Type Distribution">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={mergeDist(data.charts.content_type_distribution)}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="key" tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="person_a" name={nameA} fill={COLOR_A} radius={[4, 4, 0, 0]} animationDuration={500} />
              <Bar dataKey="person_b" name={nameB} fill={COLOR_B} radius={[4, 4, 0, 0]} animationDuration={500} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Engagement Comparison">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={engagementComparisonRows(data.charts.engagement_comparison)}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="metric" tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="person_a" name={nameA} fill={COLOR_A} radius={[4, 4, 0, 0]} animationDuration={500} />
              <Bar dataKey="person_b" name={nameB} fill={COLOR_B} radius={[4, 4, 0, 0]} animationDuration={500} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-dark">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-gold/15 text-gold-700">
            <Trophy size={13} strokeWidth={2.25} />
          </span>
          Top Performing Content
        </h3>
        <DataTable
          rows={data.charts.top_content}
          keyFn={(r) => r.content_id}
          columns={[
            { key: "person", header: "Person", render: (r) => r.person_name },
            { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span> },
            { key: "type", header: "Type", render: (r) => <span className="capitalize">{r.content_type}</span> },
            { key: "date", header: "Date", render: (r) => fmtDate(r.published_at) },
            { key: "likes", header: "Likes", render: (r) => fmtNum(r.likes), align: "right" },
            { key: "comments", header: "Comments", render: (r) => fmtNum(r.comments_count), align: "right" },
            { key: "engagement", header: "Engagement", render: (r) => fmtNum(r.engagement), align: "right" },
          ]}
        />
      </div>
    </div>
  );
}

function mergeDist(dist: { person_a: Record<string, number>; person_b: Record<string, number> }) {
  const keys = new Set([...Object.keys(dist.person_a || {}), ...Object.keys(dist.person_b || {})]);
  return Array.from(keys).map((key) => ({
    key, person_a: dist.person_a?.[key] ?? 0, person_b: dist.person_b?.[key] ?? 0,
  }));
}

function engagementComparisonRows(cmp: { person_a: Record<string, number | null>; person_b: Record<string, number | null> }) {
  const labels: Record<string, string> = {
    avg_likes: "Avg Likes", avg_comments: "Avg Comments", avg_shares: "Avg Shares", avg_engagement: "Avg Engagement",
  };
  return Object.keys(labels).map((k) => ({
    metric: labels[k], person_a: cmp.person_a?.[k] ?? 0, person_b: cmp.person_b?.[k] ?? 0,
  }));
}
