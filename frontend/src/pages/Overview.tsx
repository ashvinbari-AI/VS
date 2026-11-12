import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Users, FileText, Image, Clapperboard, Heart, MessageCircle, Eye, Flame,
} from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { KpiCompareCard } from "../components/KPI/KpiCompareCard";
import { ChartCard } from "../components/Charts/ChartCard";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { DataTable } from "../components/Tables/DataTable";
import { ProofDrawer, type ProofRequest } from "../components/Proof/ProofDrawer";
import { Section } from "../components/Layout/Section";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { comparisonDeps, comparisonParams, useFilters, type SelectedPerson } from "../state/FilterContext";
import { fmtCompact, fmtDate, fmtNum } from "../utils/format";
import { COLOR_GRID } from "../utils/theme";

type PerPerson<T> = Record<string, T>;

interface OverviewResponse {
  person_ids: string[];
  kpis: PerPerson<any>;
  charts: {
    // Rows are {date, <person_id>: value, ...}
    content_activity_timeline: Record<string, any>[];
    engagement_timeline: Record<string, any>[];
    platform_distribution: PerPerson<Record<string, number>>;
    content_type_distribution: PerPerson<Record<string, number>>;
    engagement_comparison: PerPerson<Record<string, number | null>>;
    top_content: any[];
  };
}

export default function Overview() {
  const { filters, selected, ready } = useFilters();

  const { data, loading, error, reload } = useApi<OverviewResponse>(
    () => api.get("/overview", comparisonParams(filters)),
    comparisonDeps(filters),
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && (
        <OverviewBody
          data={data} people={selected}
          proofFilters={{ platform: filters.platform, contentType: filters.contentType, dateFrom: filters.dateFrom ?? undefined }}
        />
      )}
    </AsyncBoundary>
  );
}

function OverviewBody({
  data, people, proofFilters,
}: {
  data: OverviewResponse; people: SelectedPerson[];
  proofFilters: { platform?: string; contentType?: string; dateFrom?: string };
}) {
  const [proof, setProof] = useState<ProofRequest | null>(null);

  const openProof = (metric: string, label: string) => () =>
    setProof({ people, metric, label, ...proofFilters });

  /** Every person's formatted value of one KPI, for a KpiCompareCard. */
  const kpi = (fmt: (k: any) => string) =>
    people.map((p) => ({ ...p, value: fmt(data.kpis[p.id] ?? {}) }));

  return (
    <div className="space-y-8">
      <ProofDrawer request={proof} onClose={() => setProof(null)} />
      <Section title="Key numbers" description="Click any card to see exactly how the number was calculated.">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCompareCard icon={Users} label="Followers" values={kpi((k) => fmtCompact(k.followers))} onProof={openProof("followers", "Followers")} />
        <KpiCompareCard icon={FileText} label="Total Content" values={kpi((k) => fmtNum(k.total_content))} onProof={openProof("total_content", "Total Content")} />
        <KpiCompareCard icon={Image} label="Posts" values={kpi((k) => fmtNum(k.posts))} onProof={openProof("posts", "Posts")} />
        <KpiCompareCard icon={Clapperboard} label="Reels" values={kpi((k) => fmtNum(k.reels))} onProof={openProof("reels", "Reels")} />
        <KpiCompareCard icon={Heart} label="Total Likes" values={kpi((k) => fmtNum(k.total_likes))} onProof={openProof("total_likes", "Total Likes")} />
        <KpiCompareCard icon={MessageCircle} label="Total Comments" values={kpi((k) => fmtNum(k.total_comments_count))} onProof={openProof("total_comments_count", "Total Comments")} />
        <KpiCompareCard icon={Eye} label="View Engagement" values={kpi((k) => fmtNum(k.view_engagement))} sublabel="post + reel views" onProof={openProof("view_engagement", "View Engagement")} />
        <KpiCompareCard icon={Flame} label="Total Engagement" values={kpi((k) => fmtNum(k.total_engagement))} onProof={openProof("total_engagement", "Total Engagement")} />
      </div>
      </Section>

      <Section title="Trends" description="Daily posting and engagement over the selected period.">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Content Activity Timeline">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.charts.content_activity_timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8B93A7" }} tickFormatter={(d) => fmtDate(d)} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
              <Tooltip labelFormatter={(d) => fmtDate(String(d))} contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {people.map((p) => (
                <Line key={p.id} type="monotone" dataKey={p.id} name={p.name} stroke={p.color} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} animationDuration={500} />
              ))}
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
              {people.map((p) => (
                <Line key={p.id} type="monotone" dataKey={p.id} name={p.name} stroke={p.color} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} connectNulls animationDuration={500} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

      </div>
      </Section>

      <Section title="Breakdown" description="What each person posts, and the totals it earned.">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Content Type Distribution">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={mergeDist(data.charts.content_type_distribution, people)}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="key" tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} allowDecimals={false} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {people.map((p) => (
                <Bar key={p.id} dataKey={p.id} name={p.name} fill={p.color} radius={[4, 4, 0, 0]} animationDuration={500} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Engagement Comparison">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={engagementComparisonRows(data.charts.engagement_comparison, people)}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLOR_GRID} vertical={false} />
              <XAxis dataKey="metric" tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={{ stroke: COLOR_GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#8B93A7" }} axisLine={false} tickLine={false} tickFormatter={fmtCompact} />
              <Tooltip contentStyle={{ borderRadius: 10, borderColor: COLOR_GRID, fontSize: 12 }} cursor={{ fill: "rgba(22,48,90,0.04)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {people.map((p) => (
                <Bar key={p.id} dataKey={p.id} name={p.name} fill={p.color} radius={[4, 4, 0, 0]} animationDuration={500} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      </Section>

      <Section title="Top performing content" description="The 10 highest-engagement posts across everyone selected.">
        <DataTable
          rows={data.charts.top_content}
          keyFn={(r) => r.content_id}
          defaultSortKey="engagement"
          columns={[
            { key: "person", header: "Person", render: (r) => r.person_name, sortable: true, sortValue: (r) => r.person_name },
            { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span>, sortable: true, sortValue: (r) => r.platform },
            { key: "type", header: "Type", render: (r) => <span className="capitalize">{r.content_type}</span>, sortable: true, sortValue: (r) => r.content_type },
            { key: "date", header: "Date", render: (r) => fmtDate(r.published_at), sortable: true, sortValue: (r) => r.published_at },
            { key: "likes", header: "Likes", render: (r) => fmtNum(r.likes), align: "right", sortable: true, sortValue: (r) => r.likes },
            { key: "comments", header: "Comments", render: (r) => fmtNum(r.comments_count), align: "right", sortable: true, sortValue: (r) => r.comments_count },
            { key: "engagement", header: "Engagement", render: (r) => fmtNum(r.engagement), align: "right", sortable: true, sortValue: (r) => r.engagement },
          ]}
        />
      </Section>
    </div>
  );
}

/** Union of category keys across every person; a key someone lacks is 0. */
function mergeDist(dist: PerPerson<Record<string, number>>, people: SelectedPerson[]) {
  const keys = new Set(people.flatMap((p) => Object.keys(dist[p.id] ?? {})));
  return Array.from(keys).map((key) => ({
    key,
    ...Object.fromEntries(people.map((p) => [p.id, dist[p.id]?.[key] ?? 0])),
  }));
}

function engagementComparisonRows(cmp: PerPerson<Record<string, number | null>>, people: SelectedPerson[]) {
  const labels: Record<string, string> = {
    total_likes: "Total Likes", total_comments: "Total Comments", total_shares: "Total Shares", total_engagement: "Total Engagement",
  };
  return Object.keys(labels).map((k) => ({
    metric: labels[k],
    ...Object.fromEntries(people.map((p) => [p.id, cmp[p.id]?.[k] ?? 0])),
  }));
}
