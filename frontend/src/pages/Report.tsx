import { useMemo, useRef, useState } from "react";
import { Download, Loader2, Trophy } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { comparisonDeps, comparisonParams, useFilters, type SelectedPerson } from "../state/FilterContext";
import { fmtCompact, fmtDate, fmtNum, fmtPct } from "../utils/format";
import { svgToPng } from "../utils/chartExport";
import { COLOR_GRID } from "../utils/theme";

type Row = (string | number)[];
type Dist = Record<string, number> | undefined;

/** Union of the keys across every person's distribution dict (comment
 * sentiment, theme breakdowns, ...), so a label someone doesn't have shows
 * as 0 rather than being silently dropped from the table. */
function mergeDist(dists: Dist[]): Row[] {
  const labels = Array.from(new Set(dists.flatMap((d) => Object.keys(d ?? {})))).sort();
  return labels.map((label) => [label, ...dists.map((d) => fmtNum(d?.[label] ?? 0))]);
}

/** One chart category: {name, <person_id>: value, ...}. */
type Group = { name: string } & Record<string, number | string>;

/** Same union-of-labels merge as mergeDist, but numeric so it can be charted. */
function distGroups(people: SelectedPerson[], dists: Dist[]): Group[] {
  const labels = Array.from(new Set(dists.flatMap((d) => Object.keys(d ?? {})))).sort();
  return labels.map((name) => ({
    name,
    ...Object.fromEntries(people.map((p, i) => [p.id, dists[i]?.[name] ?? 0])),
  }) as Group);
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const AXIS_TICK = { fontSize: 11, fill: "#5B6478" };
const VALUE_LABEL = { fontSize: 10, fill: "#334155" };
/** Same bar thickness on every chart, however few categories it has. */
const BAR_MAX = 36;

/** Card shell for one chart. The data-pdf-* attributes let handleDownload
 * find every rendered chart in on-screen order and place it in the PDF. */
function ChartPanel({ title, note, wide, inPdf, onTogglePdf, children }: {
  title: string; note?: string; wide?: boolean;
  /** Pass both to show an "Include in PDF" switch; off drops the chart from the download. */
  inPdf?: boolean; onTogglePdf?: (on: boolean) => void;
  children: React.ReactNode;
}) {
  const included = inPdf ?? true;
  return (
    <div
      data-pdf-chart
      data-pdf-title={title}
      data-pdf-wide={wide ? "1" : "0"}
      data-pdf-include={included ? "1" : "0"}
      className={`rounded-xl border border-silver/60 bg-white p-4 shadow-card ${wide ? "lg:col-span-2" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-dark">{title}</h3>
        {onTogglePdf && (
          <label className="flex shrink-0 cursor-pointer select-none items-center gap-2 text-xs text-dark/60">
            Include in PDF
            <button
              type="button"
              role="switch"
              aria-checked={included}
              onClick={() => onTogglePdf(!included)}
              className={`relative h-5 w-9 rounded-full transition-colors ${included ? "bg-gold" : "bg-silver"}`}
            >
              <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${included ? "left-[18px]" : "left-0.5"}`} />
            </button>
          </label>
        )}
      </div>
      {note && <p className="text-xs text-dark/50">{note}</p>}
      <div className="mt-2">{children}</div>
    </div>
  );
}

function GroupedBars({
  data, people, height = 260, suffix = "", angle = 0,
}: { data: Group[]; people: SelectedPerson[]; height?: number; suffix?: string; angle?: number }) {
  // Compact (12.5M, 43K) on the axis and bar tops so large totals fit the
  // 52px axis instead of being clipped to "000,000".
  const short = (v: number) => (suffix ? `${fmtNum(v, 1)}${suffix}` : fmtCompact(v));
  // Value labels on top of every bar get unreadable past ~3 people.
  const showLabels = people.length <= 3;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 20, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLOR_GRID} vertical={false} />
        <XAxis dataKey="name" tick={AXIS_TICK} interval={0} angle={angle} textAnchor={angle ? "end" : "middle"} height={angle ? 70 : 30} />
        <YAxis tick={AXIS_TICK} width={52} tickFormatter={short} />
        <Tooltip formatter={(v: number) => `${fmtNum(v, 2)}${suffix}`} />
        <Legend />
        {people.map((p) => (
          <Bar key={p.id} name={p.name} dataKey={p.id} fill={p.color} radius={[3, 3, 0, 0]} maxBarSize={BAR_MAX} isAnimationActive={false}>
            {showLabels && <LabelList dataKey={p.id} position="top" formatter={short} style={VALUE_LABEL} />}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function IssueBars({ rows, color }: { rows: { name: string; value: number }[]; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 30 + 30)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 44, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLOR_GRID} horizontal={false} />
        <XAxis type="number" tick={AXIS_TICK} tickFormatter={fmtCompact} />
        <YAxis type="category" dataKey="name" tick={AXIS_TICK} width={130} interval={0} />
        <Tooltip formatter={(v: number) => `${fmtNum(v)} mentions`} />
        <Bar name="Mentions" dataKey="value" fill={color} radius={[0, 3, 3, 0]} maxBarSize={18} isAnimationActive={false}>
          <LabelList dataKey="value" position="right" formatter={fmtCompact} style={VALUE_LABEL} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Headline stat: every person's value, the single leader marked with a trophy. */
function StatCard({ label, people, raw }: { label: string; people: SelectedPerson[]; raw: (id: string) => number | null | undefined }) {
  const values = people.map((p) => raw(p.id));
  const nums = values.filter((v): v is number => typeof v === "number");
  const best = nums.length === values.length && nums.length > 0 ? Math.max(...nums) : null;
  // A trophy only for a sole, complete leader -- a tie or a missing value
  // means no leader is declared (same rule as the Comparison page).
  const leaderIdx = best !== null && nums.filter((v) => v === best).length === 1 ? values.indexOf(best) : -1;
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-navy-700/70">{label}</div>
      <div className={people.length === 2 ? "flex gap-3" : "space-y-1"}>
        {people.map((p, i) => {
          const isLead = i === leaderIdx;
          return people.length === 2 ? (
            <div key={p.id} className="min-w-0 flex-1">
              <div className="flex items-center gap-1 text-[11px] text-dark/50">
                <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: p.color }} />
                <span className="truncate">{p.name}</span>
                {isLead && <Trophy size={11} className="shrink-0 text-gold-600" />}
              </div>
              <div className={`text-lg font-semibold ${isLead ? "text-dark" : "text-dark/70"}`}>{fmtNum(values[i])}</div>
            </div>
          ) : (
            <div key={p.id} className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-1 text-[11px] text-dark/60">
                <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: p.color }} />
                <span className="truncate">{p.name}</span>
                {isLead && <Trophy size={11} className="shrink-0 text-gold-600" />}
              </div>
              <div className={`text-sm font-semibold ${isLead ? "text-dark" : "text-dark/70"}`}>{fmtNum(values[i])}</div>
            </div>
          );
        })}
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
  const { filters, selected, ready } = useFilters();
  const names = selected.map((p) => p.name);

  const commonParams = comparisonParams(filters);
  const deps = comparisonDeps(filters);

  const overview = useApi<any>(() => api.get("/overview", commonParams), deps, ready);
  const engagement = useApi<any>(() => api.get("/engagement", commonParams), deps, ready);
  const sentiment = useApi<any>(() => api.get("/sentiment", commonParams), deps, ready);
  const narratives = useApi<any>(() => api.get("/narratives", commonParams), deps, ready);
  const comments = useApi<any>(
    () => api.get("/comments", { person_ids: filters.personIds, platform: filters.platform }),
    [filters.personIds.join(","), filters.platform],
    ready
  );

  const loading = overview.loading || engagement.loading || sentiment.loading || narratives.loading || comments.loading;
  const error = overview.error || engagement.error || sentiment.error || narratives.error || comments.error;
  const reloadAll = () => { overview.reload(); engagement.reload(); sentiment.reload(); narratives.reload(); comments.reload(); };

  /** One table row: label + one formatted value per selected person. */
  const perPersonRow = (label: string, source: Record<string, any> | undefined, fmt: (b: any) => string): Row =>
    [label, ...selected.map((p) => fmt(source?.[p.id] ?? {}))];

  const kpi = overview.data?.kpis as Record<string, any> | undefined;

  const kpiRows: Row[] = useMemo(() => {
    if (!kpi) return [];
    return [
      perPersonRow("Followers", kpi, (k) => fmtNum(k.followers)),
      perPersonRow("Total Content", kpi, (k) => fmtNum(k.total_content)),
      perPersonRow("Posts", kpi, (k) => fmtNum(k.posts)),
      perPersonRow("Reels", kpi, (k) => fmtNum(k.reels)),
      perPersonRow("Total Likes", kpi, (k) => fmtNum(k.total_likes)),
      perPersonRow("Avg Likes / Post", kpi, (k) => fmtNum(k.average_likes, 1)),
      perPersonRow("Total Comments", kpi, (k) => fmtNum(k.total_comments_count)),
      perPersonRow("Avg Comments / Post", kpi, (k) => fmtNum(k.average_comments, 1)),
      perPersonRow("Total Engagement", kpi, (k) => fmtNum(k.total_engagement)),
      perPersonRow("Engagement Rate", kpi, (k) => fmtPct(k.engagement_rate)),
      perPersonRow("View Engagement (post+reel)", kpi, (k) => fmtNum(k.view_engagement)),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kpi, selected]);

  const engagementRows: Row[] = useMemo(() => {
    const e = engagement.data?.people;
    if (!e) return [];
    return [
      perPersonRow("Average Engagement", e, (b) => fmtNum(b.average_engagement, 1)),
      perPersonRow("Engagement Rate", e, (b) => fmtPct(b.engagement_rate_pct)),
      perPersonRow("Engagement / 1000 Followers", e, (b) => fmtNum(b.engagement_per_1000_followers, 2)),
      perPersonRow("P90 Engagement", e, (b) => fmtNum(b.p90_engagement, 1)),
      perPersonRow("P95 Engagement", e, (b) => fmtNum(b.p95_engagement, 1)),
      perPersonRow("Top 10% Avg Engagement", e, (b) => fmtNum(b.top10_percent_avg_engagement, 1)),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagement.data, selected]);

  const topContentRows = (items: any[]): Row[] =>
    (items ?? []).map((r, i) => [i + 1, r.person_name, r.platform, fmtDate(r.published_at), fmtNum(r.likes), fmtNum(r.comments_count), fmtNum(r.engagement, 1)]);

  const topPostsRows = useMemo(() => topContentRows(engagement.data?.top_posts), [engagement.data]);
  const topReelsRows = useMemo(() => topContentRows(engagement.data?.top_reels), [engagement.data]);

  // Sentiment covers only the comments we scraped (top-level, no replies), so it
  // never adds up to the platform's comments_count -- show both totals side by side.
  const sumDist = (d?: Record<string, number>) => Object.values(d ?? {}).reduce((s, n) => s + n, 0);
  const sentimentDists: Dist[] = selected.map((p) => sentiment.data?.comment_sentiment?.[p.id]);
  const analysed = sentimentDists.map(sumDist);
  const commentSentimentRows = useMemo(() => {
    const rows = mergeDist(sentimentDists);
    if (!rows.length) return rows;
    rows.push(["Total analysed comments", ...analysed.map((n) => fmtNum(n))]);
    if (kpi) rows.push(perPersonRow("Platform-reported comments (incl. replies)", kpi, (k) => fmtNum(k.total_comments_count)));
    return rows;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sentiment.data, overview.data, selected]);
  const commentSentimentNote = kpi && analysed.some(Boolean)
    ? `Based on ${analysed.map((n) => fmtNum(n)).join(" vs ")} scraped top-level comments. The platforms report `
      + `${selected.map((p) => fmtNum(kpi[p.id]?.total_comments_count)).join(" vs ")} `
      + `(that count includes replies and comments not available to scrape).`
    : undefined;

  const narrativeRows: Row[] = useMemo(() => {
    if (!narratives.data?.analysis_available) return [];
    return (narratives.data.table ?? []).map((r: any) => [
      r.narrative,
      ...selected.flatMap((p) => [fmtNum(r.people?.[p.id]?.count), fmtPct(r.people?.[p.id]?.pct)]),
    ]);
  }, [narratives.data, selected]);

  const themeDists: Dist[] = selected.map((p) => comments.data?.people?.[p.id]?.theme_breakdown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const themeRows = useMemo(() => mergeDist(themeDists), [comments.data, selected]);
  const issuesRows = (block: any): Row[] =>
    (block?.issues ?? []).slice(0, 10).map((r: any) => [r.issue, fmtNum(r.mentions), fmtPct(r.percentage)]);
  const issueBars = (block: any) => (block?.issues ?? []).slice(0, 10).map((r: any) => ({ name: r.issue, value: r.mentions ?? 0 }));

  const [downloading, setDownloading] = useState(false);
  const [narrativeInPdf, setNarrativeInPdf] = useState(true);
  const chartsRef = useRef<HTMLDivElement>(null);

  const kpiGroups = (metrics: [string, string][]): Group[] => kpi
    ? metrics.map(([name, key]) => ({
      name,
      ...Object.fromEntries(selected.map((p) => [p.id, kpi[p.id]?.[key] ?? 0])),
    }) as Group)
    : [];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const mixGroups = useMemo(() => kpiGroups([["Posts", "posts"], ["Reels", "reels"]]), [kpi, selected]);
  const totalsGroups = useMemo(
    () => kpiGroups([["Likes", "total_likes"], ["Comments", "total_comments_count"], ["Engagement", "total_engagement"]]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [kpi, selected]
  );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const commentSentGroups = useMemo(() => distGroups(selected, sentimentDists), [sentiment.data, selected]);
  const narrativeGroups: Group[] = useMemo(
    () => narratives.data?.analysis_available
      ? (narratives.data.table ?? []).map((r: any) => ({
        name: r.narrative,
        ...Object.fromEntries(selected.map((p) => [p.id, r.people?.[p.id]?.pct ?? 0])),
      }) as Group)
      : [],
    [narratives.data, selected]
  );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const themeGroups = useMemo(() => distGroups(selected, themeDists), [comments.data, selected]);

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
    const pageWidth = doc.internal.pageSize.getWidth();
    let y = 50;

    doc.setFontSize(18);
    doc.text("Political Intelligence -- Comparison Report", marginX, y);
    y += 20;
    doc.setFontSize(10);
    doc.setTextColor(90);
    const titleLines = doc.splitTextToSize(names.join("  vs  "), pageWidth - marginX * 2) as string[];
    doc.text(titleLines, marginX, y);
    y += 14 * titleLines.length;
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
    const usableW = pageWidth - marginX * 2;
    const gap = 14;
    const halfW = (usableW - gap) / 2;
    const nodes = Array.from(chartsRef.current?.querySelectorAll<HTMLElement>('[data-pdf-chart][data-pdf-include="1"]') ?? []);
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
      // The on-screen legends are HTML (not in the SVG), so draw one shared
      // key -- one color swatch per person, wrapping onto a new line as needed.
      doc.setFontSize(9);
      let lx = marginX;
      selected.forEach((p) => {
        const w = 12 + doc.getTextWidth(p.name) + 18;
        if (lx + w > pageWidth - marginX) { lx = marginX; y += 14; }
        doc.setFillColor(...hexToRgb(p.color));
        doc.rect(lx, y - 7, 8, 8, "F");
        doc.text(p.name, lx + 12, y);
        lx += w;
      });
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
        styles: { fontSize: selected.length > 3 ? 7.5 : 8.5, cellPadding: 4 },
        headStyles: { fillColor: [15, 40, 80] },
        theme: "striped",
      });
      y = (doc as any).lastAutoTable.finalY + 26;
    };

    section("Overview KPIs", ["Metric", ...names], kpiRows);
    section("Engagement Summary", ["Metric", ...names], engagementRows);
    section("Top Posts (by engagement)", ["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"], topPostsRows);
    section("Top Reels (by engagement)", ["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"], topReelsRows);
    section("Comment Sentiment", ["Sentiment", ...names], commentSentimentRows);
    section("Narrative Breakdown", narrativeHead, narrativeRows);
    section("Comment Theme Breakdown", ["Theme", ...names], themeRows);
    selected.forEach((p) => {
      section(`Top Public Issues -- ${p.name}`, ["Issue", "Mentions", "% of Comments"], issuesRows(comments.data?.people?.[p.id]));
    });

    const stamp = new Date().toISOString().slice(0, 10);
    const safe = (s: string) => s.replace(/[^a-z0-9]+/gi, "_");
    doc.save(`report_${names.map(safe).join("_vs_")}_${stamp}.pdf`);
  };

  const narrativeHead = ["Narrative", ...names.flatMap((n) => [`${n} Count`, `${n} %`])];

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reloadAll}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-silver/60 bg-white p-4 shadow-card">
          <div>
            <h1 className="text-lg font-semibold text-dark">Overall Report -- {names.join(" vs ")}</h1>
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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard label="Followers" people={selected} raw={(id) => kpi[id]?.followers} />
            <StatCard label="Total Content" people={selected} raw={(id) => kpi[id]?.total_content} />
            <StatCard label="Total Engagement" people={selected} raw={(id) => kpi[id]?.total_engagement} />
          </div>
        )}

        <SectionHeading>Visual comparison</SectionHeading>
        <div ref={chartsRef} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {mixGroups.length > 0 && (
            <ChartPanel title="Content Mix (Posts vs Reels)">
              <GroupedBars data={mixGroups} people={selected} />
            </ChartPanel>
          )}
          {/* One chart per total -- on a shared axis, comments (thousands) were
              invisible next to likes/engagement (millions). */}
          {totalsGroups.map((g) => (
            <ChartPanel key={g.name} title={`Total ${g.name}`}>
              <GroupedBars data={[g]} people={selected} />
            </ChartPanel>
          ))}
          {commentSentGroups.length > 0 && (
            <ChartPanel title="Comment Sentiment" note={commentSentimentNote}>
              <GroupedBars data={commentSentGroups} people={selected} />
            </ChartPanel>
          )}
          {narrativeGroups.length > 0 && (
            <ChartPanel title="Narrative Share (% of content)" wide inPdf={narrativeInPdf} onTogglePdf={setNarrativeInPdf}>
              <GroupedBars data={narrativeGroups} people={selected} suffix="%" angle={-25} height={300} />
            </ChartPanel>
          )}
          {themeGroups.length > 0 && (
            <ChartPanel title="Comment Themes" wide>
              <GroupedBars data={themeGroups} people={selected} angle={-25} height={300} />
            </ChartPanel>
          )}
          {selected.map((p) => {
            const bars = issueBars(comments.data?.people?.[p.id]);
            return bars.length > 0 ? (
              <ChartPanel key={p.id} title={`Top Public Issues -- ${p.name}`}>
                <IssueBars rows={bars} color={p.color} />
              </ChartPanel>
            ) : null;
          })}
        </div>

        <SectionHeading>Detailed data</SectionHeading>

        <Section title="Overview KPIs" head={["Metric", ...names]} rows={kpiRows} />
        <Section title="Engagement Summary" head={["Metric", ...names]} rows={engagementRows} />
        <Section title="Top Posts (by engagement)" head={["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"]} rows={topPostsRows} />
        <Section title="Top Reels (by engagement)" head={["#", "Person", "Platform", "Date", "Likes", "Comments", "Engagement"]} rows={topReelsRows} />
        <Section title="Comment Sentiment" head={["Sentiment", ...names]} rows={commentSentimentRows} />
        <Section title="Narrative Breakdown" head={narrativeHead} rows={narrativeRows} />
        <Section title="Comment Theme Breakdown" head={["Theme", ...names]} rows={themeRows} />
        {selected.map((p) => (
          <Section key={p.id} title={`Top Public Issues -- ${p.name}`} head={["Issue", "Mentions", "% of Comments"]} rows={issuesRows(comments.data?.people?.[p.id])} />
        ))}
      </div>
    </AsyncBoundary>
  );
}
