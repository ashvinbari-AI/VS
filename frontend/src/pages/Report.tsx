import { useMemo } from "react";
import { Download } from "lucide-react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDate, fmtNum, fmtPct } from "../utils/format";

type Row = (string | number)[];

/** Union of the keys across both distribution dicts (post/comment sentiment,
 * theme breakdowns, ...), so a label either side doesn't have shows as 0
 * rather than being silently dropped from the table. */
function mergeDist(a: Record<string, number> | undefined, b: Record<string, number> | undefined): Row[] {
  const labels = Array.from(new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})])).sort();
  return labels.map((label) => [label, fmtNum(a?.[label] ?? 0), fmtNum(b?.[label] ?? 0)]);
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

  const loading = overview.loading || engagement.loading || sentiment.loading || narratives.loading || comments.loading;
  const error = overview.error || engagement.error || sentiment.error || narratives.error || comments.error;
  const reloadAll = () => { overview.reload(); engagement.reload(); sentiment.reload(); narratives.reload(); comments.reload(); };

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

  const handleDownload = () => {
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
            className="flex items-center gap-1.5 rounded-md bg-gold px-3 py-2 text-xs font-semibold text-navy-900 hover:brightness-95"
          >
            <Download size={14} /> Download PDF
          </button>
        </div>

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
