import { useMemo, useRef, useState } from "react";
import { Download, Loader2, Trophy } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDate, fmtNum, fmtPct } from "../utils/format";
import { svgToPng } from "../utils/chartExport";
import { COLOR_GRID, COLOR_PRIMARY, COLOR_SECONDARY } from "../utils/theme";

type Row = (string | number)[];

/** Union of the keys across both distribution dicts (post/comment sentiment,
 * theme breakdowns, ...), so a label either side doesn't have shows as 0
 * rather than being silently dropped from the table. */
function mergeDist(a: Record<string, number> | undefined, b: Record<string, number> | undefined): Row[] {
  const labels = Array.from(new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})])).sort();
  return labels.map((label) => [label, fmtNum(a?.[label] ?? 0), fmtNum(b?.[label] ?? 0)]);
}

type Pair = { name: string; a: number; b: number };

/** Same union-of-labels merge as mergeDist, but numeric so it can be charted. */
function distPairs(a: Record<string, number> | undefined, b: Record<string, number> | undefined): Pair[] {
  const labels = Array.from(new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})])).sort();
  return labels.map((name) => ({ name, a: a?.[name] ?? 0, b: b?.[name] ?? 0 }));
}

const AXIS_TICK = { fontSize: 11, fill: "#5B6478" };

/** Card shell for one chart. The data-pdf-* attributes let handleDownload
 * find every rendered chart in on-screen order and place it in the PDF. */
function ChartPanel({ title, note, wide, children }: { title: string; note?: string; wide?: boolean; children: React.ReactNode }) {
  return (
    <div
      data-pdf-chart
      data-pdf-title={title}
      data-pdf-wide={wide ? "1" : "0"}
      className={`rounded-xl border border-silver/60 bg-white p-4 shadow-card ${wide ? "lg:col-span-2" : ""}`}
    >
      <h3 className="text-sm font-semibold text-dark">{title}</h3>
      {note && <p className="text-xs text-dark/50">{note}</p>}
      <div className="mt-2">{children}</div>
    </div>
  );
}

function GroupedBars({
  data, nameA, nameB, height = 260, suffix = "", angle = 0,
}: { data: Pair[]; nameA: string; nameB: string; height?: number; suffix?: string; angle?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLOR_GRID} vertical={false} />
        <XAxis dataKey="name" tick={AXIS_TICK} interval={0} angle={angle} textAnchor={angle ? "end" : "middle"} height={angle ? 70 : 30} />
        <YAxis tick={AXIS_TICK} width={52} tickFormatter={(v) => `${fmtNum(v, 0)}${suffix}`} />
        <Tooltip formatter={(v: number) => `${fmtNum(v, 2)}${suffix}`} />
        <Legend />
        <Bar name={nameA} dataKey="a" fill={COLOR_PRIMARY} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        <Bar name={nameB} dataKey="b" fill={COLOR_SECONDARY} radius={[3, 3, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function IssueBars({ rows, color }: { rows: { name: string; value: number }[]; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 30 + 30)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLOR_GRID} horizontal={false} />
        <XAxis type="number" tick={AXIS_TICK} />
        <YAxis type="category" dataKey="name" tick={AXIS_TICK} width={130} interval={0} />
        <Tooltip formatter={(v: number) => `${fmtNum(v)} mentions`} />
        <Bar name="Mentions" dataKey="value" fill={color} radius={[0, 3, 3, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Headline stat: both people's value side by side, leader marked with a trophy. */
function StatCard({ label, a, b, nameA, nameB, lead }: { label: string; a: string; b: string; nameA: string; nameB: string; lead: "a" | "b" | null }) {
  const cell = (color: string, name: string, value: string, isLead: boolean) => (
    <div className="min-w-0 flex-1">
      <div className="flex items-center gap-1 text-[11px] text-dark/50">
        <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
        <span className="truncate">{name}</span>
        {isLead && <Trophy size={11} className="shrink-0 text-gold-600" />}
      </div>
      <div className={`text-lg font-semibold ${isLead ? "text-dark" : "text-dark/70"}`}>{value}</div>
    </div>
  );
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-navy-700/70">{label}</div>
      <div className="flex gap-3">
        {cell(COLOR_PRIMARY, nameA, a, lead === "a")}
        {cell(COLOR_SECONDARY, nameB, b, lead === "b")}
      </div>
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="border-l-4 border-gold pl-2 text-sm font-semibold uppercase tracking-wide text-navy-700">{children}</h2>;
}

function Section({ title, head, rows }: { title: string; head: string[]; rows: Row[] }) {
  if (!rows.length) return null;
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-silver/60 text-left text-xs font-semibold uppercase tracking-wide text-navy-700/70">
              {head.map((h) => (
                <th key={h} className="px-2 py-1.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-silver/30 last:border-0">
                {row.map((cell, j) => (
                  <td key={j} className="px-2 py-1.5">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Report() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;

  const commonParams = {
    person_a: filters.personA, person_b: filters.personB, platform: filters.platform,
    content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
  };
  const deps = [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom, filters.dateTo];

  const overview = useApi<any>(() => api.get("/overview", commonParams), deps, ready);
  const engagement = useApi<any>(() => api.get("/engagement", commonParams), deps, ready);
  const sentiment = useApi<any>(() => api.get("/sentiment", commonParams), deps, ready);
  const narratives = useApi<any>(() => api.get("/narratives", commonParams), deps, ready);
  const comments = useApi<any>(
    () => api.get("/comments", { person_a: filters.personA, person_b: filters.personB, platform: filters.platform }),
    [filters.personA, filters.personB, filters.platform],
    ready
  );

  // Feeds the radar only -- a failure here shouldn't block the rest of the report.
  const comparison = useApi<any>(
    () => api.get("/comparison", { ...commonParams, period_days: filters.periodDays }),
    [...deps, filters.periodDays],
    ready
  );

  const loading = comparison.loading || overview.loading || engagement.loading || sentiment.loading || narratives.loading || comments.loading;
  const error = overview.error || engagement.error || sentiment.error || narratives.error || comments.error;
  const reloadAll = () => { overview.reload(); engagement.reload(); sentiment.reload(); narratives.reload(); comments.reload(); comparison.reload(); };

  const kpiRows: Row[] = useMemo(() => {
    if (!overview.data) return [];
    const a = overview.data.kpis.person_a, b = overview.data.kpis.person_b;
    return [
      ["Followers", fmtNum(a.followers), fmtNum(b.followers)],
      ["Total Content", fmtNum(a.total_content), fmtNum(b.total_content)],
      ["Posts", fmtNum(a.posts), fmtNum(b.posts)],
      ["Reels", fmtNum(a.reels), fmtNum(b.reels)],
      ["Total Likes", fmtNum(a.total_likes), fmtNum(b.total_likes)],
      ["Avg Likes / Post", fmtNum(a.average_likes, 1), fmtNum(b.average_likes, 1)],
      ["Total Comments", fmtNum(a.total_comments_count), fmtNum(b.total_comments_count)],
      ["Avg Comments / Post", fmtNum(a.average_comments, 1), fmtNum(b.average_comments, 1)],
      ["Total Engagement", fmtNum(a.total_engagement), fmtNum(b.total_engagement)],
      ["Engagement Rate", fmtPct(a.engagement_rate), fmtPct(b.engagement_rate)],
      ["View Engagement (post+reel)", fmtNum(a.view_engagement), fmtNum(b.view_engagement)],
    ];
  }, [overview.data]);

  const engagementRows: Row[] = useMemo(() => {
    if (!engagement.data) return [];
    const a = engagement.data.person_a, b = engagement.data.person_b;
    return [
      ["Average Engagement", fmtNum(a.average_engagement, 1), fmtNum(b.average_engagement, 1)],
      ["Engagement Rate", fmtPct(a.engagement_rate_pct), fmtPct(b.engagement_rate_pct)],
      ["Engagement / 1000 Followers", fmtNum(a.engagement_per_1000_followers, 2), fmtNum(b.engagement_per_1000_followers, 2)],
      ["P90 Engagement", fmtNum(a.p90_engagement, 1), fmtNum(b.p90_engagement, 1)],
      ["P95 Engagement", fmtNum(a.p95_engagement, 1), fmtNum(b.p95_engagement, 1)],
      ["Top 10% Avg Engagement", fmtNum(a.top10_percent_avg_engagement, 1), fmtNum(b.top10_percent_avg_engagement, 1)],
    ];
  }, [engagement.data]);

  const topContentRows = (items: any[]): Row[] =>
    (items ?? []).map((r, i) => [i + 1, r.person_name, r.platform, fmtDate(r.published_at), fmtNum(r.likes), fmtNum(r.comments_count), fmtNum(r.engagement, 1)]);

  const topPostsRows = useMemo(() => topContentRows(engagement.data?.top_posts), [engagement.data]);
  const topReelsRows = useMemo(() => topContentRows(engagement.data?.top_reels), [engagement.data]);

  const postSentimentRows = useMemo(
    () => mergeDist(sentiment.data?.post_sentiment?.person_a, sentiment.data?.post_sentiment?.person_b),
    [sentiment.data]
  );
  const commentSentimentRows = useMemo(
    () => mergeDist(sentiment.data?.comment_sentiment?.person_a, sentiment.data?.comment_sentiment?.person_b),
    [sentiment.data]
  );

  const narrativeRows: Row[] = useMemo(() => {
    if (!narratives.data?.analysis_available) return [];
    return (narratives.data.table ?? []).map((r: any) => [
      r.narrative, fmtNum(r.person_a_count), fmtPct(r.person_a_pct), fmtNum(r.person_b_count), fmtPct(r.person_b_pct),
    ]);
  }, [narratives.data]);

  const themeRows = useMemo(
    () => mergeDist(comments.data?.person_a?.theme_breakdown, comments.data?.person_b?.theme_breakdown),
    [comments.data]
  );
  const issuesRows = (block: any): Row[] =>
    (block?.issues ?? []).slice(0, 10).map((r: any) => [r.issue, fmtNum(r.mentions), fmtPct(r.percentage)]);
  const issuesARows = useMemo(() => issuesRows(comments.data?.person_a), [comments.data]);
  const issuesBRows = useMemo(() => issuesRows(comments.data?.person_b), [comments.data]);

  const [downloading, setDownloading] = useState(false);
  const chartsRef = useRef<HTMLDivElement>(null);

  const kpi = overview.data?.kpis;
  const lead = (a?: number | null, b?: number | null): "a" | "b" | null =>
    typeof a === "number" && typeof b === "number" && a !== b ? (a > b ? "a" : "b") : null;

  const radarData = useMemo(
    () => Object.entries(comparison.data?.normalized_analytics_index?.dimensions ?? {}).map(([dimension, v]: [string, any]) => ({
      dimension, a: v.person_a ?? 0, b: v.person_b ?? 0,
    })),
    [comparison.data]
  );
  const mixPairs: Pair[] = useMemo(() => kpi ? [
    { name: "Posts", a: kpi.person_a.posts ?? 0, b: kpi.person_b.posts ?? 0 },
    { name: "Reels", a: kpi.person_a.reels ?? 0, b: kpi.person_b.reels ?? 0 },
  ] : [], [kpi]);
  const totalsPairs: Pair[] = useMemo(() => kpi ? [
    { name: "Likes", a: kpi.person_a.total_likes ?? 0, b: kpi.person_b.total_likes ?? 0 },
    { name: "Comments", a: kpi.person_a.total_comments_count ?? 0, b: kpi.person_b.total_comments_count ?? 0 },
    { name: "Engagement", a: kpi.person_a.total_engagement ?? 0, b: kpi.person_b.total_engagement ?? 0 },
  ] : [], [kpi]);
  const avgPairs: Pair[] = useMemo(() => kpi ? [
    { name: "Avg Likes", a: kpi.person_a.average_likes ?? 0, b: kpi.person_b.average_likes ?? 0 },
    { name: "Avg Comments", a: kpi.person_a.average_comments ?? 0, b: kpi.person_b.average_comments ?? 0 },
  ] : [], [kpi]);
  const engPairs: Pair[] = useMemo(() => {
    const a = engagement.data?.person_a, b = engagement.data?.person_b;
    if (!a || !b) return [];
    return [
      { name: "Average", a: a.average_engagement ?? 0, b: b.average_engagement ?? 0 },
      { name: "P90", a: a.p90_engagement ?? 0, b: b.p90_engagement ?? 0 },
      { name: "P95", a: a.p95_engagement ?? 0, b: b.p95_engagement ?? 0 },
      { name: "Top 10% avg", a: a.top10_percent_avg_engagement ?? 0, b: b.top10_percent_avg_engagement ?? 0 },
    ];
  }, [engagement.data]);
  const postSentPairs = useMemo(() => distPairs(sentiment.data?.post_sentiment?.person_a, sentiment.data?.post_sentiment?.person_b), [sentiment.data]);
  const commentSentPairs = useMemo(() => distPairs(sentiment.data?.comment_sentiment?.person_a, sentiment.data?.comment_sentiment?.person_b), [sentiment.data]);
  const narrativePairs: Pair[] = useMemo(
    () => narratives.data?.analysis_available
      ? (narratives.data.table ?? []).map((r: any) => ({ name: r.narrative, a: r.person_a_pct ?? 0, b: r.person_b_pct ?? 0 }))
      : [],
    [narratives.data]
  );
  const themePairs = useMemo(() => distPairs(comments.data?.person_a?.theme_breakdown, comments.data?.person_b?.theme_breakdown), [comments.data]);
  const issueBars = (block: any) => (block?.issues ?? []).slice(0, 10).map((r: any) => ({ name: r.issue, value: r.mentions ?? 0 }));
  const issuesABars = useMemo(() => issueBars(comments.data?.person_a), [comments.data]);
  const issuesBBars = useMemo(() => issueBars(comments.data?.person_b), [comments.data]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await buildPdf();
    } finally {
      setDownloading(false);
    }
  };

  const buildPdf = async () => {
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const marginX = 40;
    const pageHeight = doc.internal.pageSize.getHeight();
    let y = 50;

    doc.setFontSize(18);
    doc.text("Political Intelligence -- Comparison Report", marginX, y);
    y += 20;
    doc.setFontSize(10);
    doc.setTextColor(90);
    doc.text(`${personAName}  vs  ${personBName}`, marginX, y);
    y += 14;
    doc.text(
      `Platform: ${filters.platform}   |   Content: ${filters.contentType}   |   Window: ${filters.dateFrom ?? "all time"} - ${filters.dateTo ?? "now"}`,
      marginX, y
    );
    y += 14;
    doc.text(`Generated ${new Date().toLocaleString()}`, marginX, y);
    doc.setTextColor(20);
    y += 10;

    // Visual comparison: every chart currently on screen, two per row
    // (full-width ones get their own row), ahead of the data tables.
    const usableW = doc.internal.pageSize.getWidth() - marginX * 2;
    const gap = 14;
    const halfW = (usableW - gap) / 2;
    const nodes = Array.from(chartsRef.current?.querySelectorAll<HTMLElement>("[data-pdf-chart]") ?? []);
    const captured = await Promise.all(nodes.map(async (n) => {
      const svg = n.querySelector<SVGSVGElement>("svg.recharts-surface");
      if (!svg) return null;
      try {
        return { title: n.dataset.pdfTitle ?? "", wide: n.dataset.pdfWide === "1", img: await svgToPng(svg) };
      } catch {
        return null;
      }
    }));
    const charts = captured.filter((c): c is NonNullable<typeof c> => !!c);
    if (charts.length) {
      y += 26;
      doc.setFontSize(13);
      doc.text("Visual Comparison", marginX, y);
      y += 16;
      // The on-screen legends are HTML (not in the SVG), so draw one shared key.
      doc.setFontSize(9);
      doc.setFillColor(22, 48, 90);
      doc.rect(marginX, y - 7, 8, 8, "F");
      doc.text(personAName, marginX + 12, y);
      const bx = marginX + 12 + doc.getTextWidth(personAName) + 18;
      doc.setFillColor(245, 166, 35);
      doc.rect(bx, y - 7, 8, 8, "F");
      doc.text(personBName, bx + 12, y);
      y += 14;

      const heightAt = (c: (typeof charts)[number], w: number) => (c.img.height / c.img.width) * w + 30;
      let i = 0;
      while (i < charts.length) {
        const solo = charts[i].wide || i === charts.length - 1 || charts[i + 1].wide;
        const row = solo ? [charts[i]] : [charts[i], charts[i + 1]];
        const w = solo && charts[i].wide ? usableW : halfW;
        const h = Math.max(...row.map((c) => heightAt(c, w)));
        if (y + h > pageHeight - 40) { doc.addPage(); y = 50; }
        row.forEach((c, k) => {
          const x = marginX + k * (halfW + gap);
          doc.setFontSize(10);
          doc.text(c.title, x, y + 10);
          doc.addImage(c.img.url, "PNG", x, y + 16, w, heightAt(c, w) - 30);
        });
        y += h + 8;
        i += row.length;
      }
      doc.addPage();
      y = 50;
    }

    const section = (title: string, head: string[], body: Row[]) => {
      if (!body.length) return;
      if (y > pageHeight - 120) { doc.addPage(); y = 50; }
      doc.setFontSize(12);
      doc.text(title, marginX, y + 16);
      autoTable(doc, {
        startY: y + 22,
        head: [head],
        body: body as (string | number)[][],
        margin: { left: marginX, right: marginX },
        styles: { fontSize: 8.5, cellPadding: 4 },
        headStyles: { fillColor: [15, 40, 80] },
        theme: "striped",
      });
      y = (doc as any).lastAutoTable.finalY + 26;
    };

    section("Overview KPIs", ["Metric", personAName, personBName], kpiRows);
    section("Engagement Summary", ["Metric", personAName, personBName], engagementRows);
    section("Top Posts (by engagement)", ["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"], topPostsRows);
    section("Top Reels (by engagement)", ["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"], topReelsRows);
    section("Post Sentiment", ["Sentiment", personAName, personBName], postSentimentRows);
    section("Comment Sentiment", ["Sentiment", personAName, personBName], commentSentimentRows);
    section("Narrative Breakdown", ["Narrative", `${personAName} Count`, `${personAName} %`, `${personBName} Count`, `${personBName} %`], narrativeRows);
    section("Comment Theme Breakdown", ["Theme", personAName, personBName], themeRows);
    section(`Top Public Issues -- ${personAName}`, ["Issue", "Mentions", "% of Comments"], issuesARows);
    section(`Top Public Issues -- ${personBName}`, ["Issue", "Mentions", "% of Comments"], issuesBRows);

    const stamp = new Date().toISOString().slice(0, 10);
    const safe = (s: string) => s.replace(/[^a-z0-9]+/gi, "_");
    doc.save(`report_${safe(personAName)}_vs_${safe(personBName)}_${stamp}.pdf`);
  };

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reloadAll}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-silver/60 bg-white p-4 shadow-card">
          <div>
            <h1 className="text-lg font-semibold text-dark">Overall Report -- {personAName} vs {personBName}</h1>
            <p className="text-xs text-dark/50">
              Platform: {filters.platform} · Content: {filters.contentType} · Window: {filters.dateFrom ?? "all time"} - {filters.dateTo ?? "now"}
            </p>
          </div>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 rounded-md bg-gold px-3 py-2 text-xs font-semibold text-navy-900 hover:brightness-95 disabled:opacity-60"
          >
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {downloading ? "Building PDF..." : "Download PDF"}
          </button>
        </div>

        {kpi && (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Followers" nameA={personAName} nameB={personBName}
              a={fmtNum(kpi.person_a.followers)} b={fmtNum(kpi.person_b.followers)} lead={lead(kpi.person_a.followers, kpi.person_b.followers)} />
            <StatCard label="Total Content" nameA={personAName} nameB={personBName}
              a={fmtNum(kpi.person_a.total_content)} b={fmtNum(kpi.person_b.total_content)} lead={lead(kpi.person_a.total_content, kpi.person_b.total_content)} />
            <StatCard label="Engagement Rate" nameA={personAName} nameB={personBName}
              a={fmtPct(kpi.person_a.engagement_rate)} b={fmtPct(kpi.person_b.engagement_rate)} lead={lead(kpi.person_a.engagement_rate, kpi.person_b.engagement_rate)} />
            <StatCard label="Total Engagement" nameA={personAName} nameB={personBName}
              a={fmtNum(kpi.person_a.total_engagement)} b={fmtNum(kpi.person_b.total_engagement)} lead={lead(kpi.person_a.total_engagement, kpi.person_b.total_engagement)} />
          </div>
        )}

        <SectionHeading>Visual comparison</SectionHeading>
        <div ref={chartsRef} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {radarData.length > 0 && (
            <ChartPanel title="Overall Comparison (Normalized Index)" note={comparison.data?.normalized_analytics_index?.note} wide>
              <ResponsiveContainer width="100%" height={340}>
                <RadarChart data={radarData} outerRadius={120}>
                  <PolarGrid stroke={COLOR_GRID} />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: "#5B6478" }} />
                  <PolarRadiusAxis tick={{ fontSize: 9, fill: "#8B93A7" }} axisLine={false} />
                  <Tooltip formatter={(v: number) => fmtNum(v, 1)} />
                  <Legend />
                  <Radar name={personAName} dataKey="a" stroke={COLOR_PRIMARY} fill={COLOR_PRIMARY} fillOpacity={0.25} isAnimationActive={false} />
                  <Radar name={personBName} dataKey="b" stroke={COLOR_SECONDARY} fill={COLOR_SECONDARY} fillOpacity={0.35} isAnimationActive={false} />
                </RadarChart>
              </ResponsiveContainer>
            </ChartPanel>
          )}
          {mixPairs.length > 0 && (
            <ChartPanel title="Content Mix (Posts vs Reels)">
              <GroupedBars data={mixPairs} nameA={personAName} nameB={personBName} />
            </ChartPanel>
          )}
          {totalsPairs.length > 0 && (
            <ChartPanel title="Total Likes, Comments & Engagement">
              <GroupedBars data={totalsPairs} nameA={personAName} nameB={personBName} />
            </ChartPanel>
          )}
          {avgPairs.length > 0 && (
            <ChartPanel title="Average Likes & Comments per Post">
              <GroupedBars data={avgPairs} nameA={personAName} nameB={personBName} />
            </ChartPanel>
          )}
          {engPairs.length > 0 && (
            <ChartPanel title="Engagement Distribution">
              <GroupedBars data={engPairs} nameA={personAName} nameB={personBName} />
            </ChartPanel>
          )}
          {postSentPairs.length > 0 && (
            <ChartPanel title="Post Sentiment">
              <GroupedBars data={postSentPairs} nameA={personAName} nameB={personBName} />
            </ChartPanel>
          )}
          {commentSentPairs.length > 0 && (
            <ChartPanel title="Comment Sentiment">
              <GroupedBars data={commentSentPairs} nameA={personAName} nameB={personBName} />
            </ChartPanel>
          )}
          {narrativePairs.length > 0 && (
            <ChartPanel title="Narrative Share (% of content)" wide>
              <GroupedBars data={narrativePairs} nameA={personAName} nameB={personBName} suffix="%" angle={-25} height={300} />
            </ChartPanel>
          )}
          {themePairs.length > 0 && (
            <ChartPanel title="Comment Themes" wide>
              <GroupedBars data={themePairs} nameA={personAName} nameB={personBName} angle={-25} height={300} />
            </ChartPanel>
          )}
          {issuesABars.length > 0 && (
            <ChartPanel title={`Top Public Issues -- ${personAName}`}>
              <IssueBars rows={issuesABars} color={COLOR_PRIMARY} />
            </ChartPanel>
          )}
          {issuesBBars.length > 0 && (
            <ChartPanel title={`Top Public Issues -- ${personBName}`}>
              <IssueBars rows={issuesBBars} color={COLOR_SECONDARY} />
            </ChartPanel>
          )}
        </div>

        <SectionHeading>Detailed data</SectionHeading>

        <Section title="Overview KPIs" head={["Metric", personAName, personBName]} rows={kpiRows} />
        <Section title="Engagement Summary" head={["Metric", personAName, personBName]} rows={engagementRows} />
        <Section title="Top Posts (by engagement)" head={["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"]} rows={topPostsRows} />
        <Section title="Top Reels (by engagement)" head={["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"]} rows={topReelsRows} />
        <Section title="Post Sentiment" head={["Sentiment", personAName, personBName]} rows={postSentimentRows} />
        <Section title="Comment Sentiment" head={["Sentiment", personAName, personBName]} rows={commentSentimentRows} />
        <Section title="Narrative Breakdown" head={["Narrative", `${personAName} Count`, `${personAName} %`, `${personBName} Count`, `${personBName} %`]} rows={narrativeRows} />
        <Section title="Comment Theme Breakdown" head={["Theme", personAName, personBName]} rows={themeRows} />
        <Section title={`Top Public Issues -- ${personAName}`} head={["Issue", "Mentions", "% of Comments"]} rows={issuesARows} />
        <Section title={`Top Public Issues -- ${personBName}`} head={["Issue", "Mentions", "% of Comments"]} rows={issuesBRows} />
      </div>
    </AsyncBoundary>
  );
}
