import { ExternalLink, X } from "lucide-react";
import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { api } from "../../services/api";
import { fmtDate, fmtNum, fmtPct } from "../../utils/format";
import { DataTable, type Column } from "../Tables/DataTable";
import { ContentDrawer } from "../ContentDrawer/ContentDrawer";
import type { SelectedPerson } from "../../state/FilterContext";

export interface ProofRequest {
  metric: string;
  label: string;
  /** Every person whose evidence to show, side by side. */
  people: SelectedPerson[];
  platform?: string;
  contentType?: string;
  dateFrom?: string;
  /** Only the Activity page's frequency metrics (posts/reels per day or
   * week) need this -- it's the denominator in their formula. */
  periodDays?: number;
}

interface ProofResponse {
  person_id: string;
  person_name: string;
  metric: string;
  formula: string;
  // A string for most_active_day ("Saturday"); every other metric is
  // numeric (most_active_hour included -- that's the hour number).
  value: number | string | null;
  sum?: number | null;
  count?: number;
  followers?: number | null;
  average_engagement?: number | null;
  period_days?: number;
  records: any[];
}

const GAP_METRICS = new Set(["longest_inactive_period_days", "median_interval_hours"]);
const DISTRIBUTION_METRICS = new Set(["most_active_day", "most_active_hour"]);

/** One click, every selected person. Each panel fetches and render independently (a
 * slow/failed fetch for one person never blocks the others) -- the evidence
 * trail behind a KPI number, calling the exact same app.analytics.engine
 * function the card itself was built from (backend/app/routers/proof.py). */
export function ProofDrawer({ request, onClose }: { request: ProofRequest | null; onClose: () => void }) {
  // Which post's real comments are open, on top of this drawer -- the
  // evidence table only ever shows counts (comments_count), so reading the
  // actual comment text means drilling one level further into the same
  // ContentDrawer the Content page uses. Shared across both people's panels
  // since only one can be open at a time.
  const [openContentId, setOpenContentId] = useState<string | null>(null);

  if (!request) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-5xl overflow-y-auto bg-white shadow-xl dark:bg-navy-900" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-silver/60 bg-white px-5 py-3 dark:border-navy-700 dark:bg-navy-900">
          <div>
            <h2 className="text-sm font-semibold text-dark dark:text-white">{request.label} — Calculation Evidence</h2>
            <div className="text-xs text-dark/50 dark:text-silver/50">{request.people.map((p) => p.name).join(" vs ")}</div>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-silver/20 dark:hover:bg-navy-700"><X size={18} /></button>
        </div>

        <div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-2">
          {request.people.map((p) => (
            <PersonProof key={p.id} request={request} personId={p.id} personName={p.name} color={p.color} onOpenContent={setOpenContentId} />
          ))}
        </div>
      </div>
      {/* Own click-catcher so a click inside it doesn't also close the
          ProofDrawer underneath -- ContentDrawer already stopPropagation()s
          on its own panel, this just covers its backdrop. */}
      <div onClick={(e) => e.stopPropagation()}>
        <ContentDrawer contentId={openContentId} onClose={() => setOpenContentId(null)} />
      </div>
    </div>
  );
}

function PersonProof({
  request, personId, personName, color, onOpenContent,
}: { request: ProofRequest; personId: string; personName: string; color: string; onOpenContent: (contentId: string) => void }) {
  const { data, loading, error } = useApi<ProofResponse>(
    () =>
      api.get("/proof", {
        person_id: personId, metric: request.metric,
        platform: request.platform, content_type: request.contentType, date_from: request.dateFrom,
        period_days: request.periodDays,
      }),
    [personId, request.metric, request.platform, request.contentType, request.dateFrom, request.periodDays],
    !!personId
  );

  // Each panel is tinted with that person's slot color (border + a faint
  // wash) so it's obvious which evidence belongs to whom.
  const accentStyle = { borderColor: `${color}55`, backgroundColor: `${color}0D` };

  const isFollowers = request.metric === "followers";
  const isGap = GAP_METRICS.has(request.metric);
  const isDistribution = DISTRIBUTION_METRICS.has(request.metric);
  const columns = columnsForMetric(request.metric);
  const keyFn = isFollowers
    ? (r: any) => `${r.run_id}_${r.platform}`
    : isGap
      ? (r: any) => `${r.from_content_id}_${r.to_content_id}`
      : isDistribution
        ? (r: any) => r.label
        : (r: any) => r.content_id;
  const recordsLabel = isFollowers ? "Snapshot" : isGap ? "Gaps Between Posts" : isDistribution ? "Full Distribution" : "Contributing Posts";
  const emptyLabel = isFollowers ? "profile snapshot" : isGap ? "gaps" : isDistribution ? "activity" : "posts";
  // Only this default (non-followers/gap/distribution) row shape actually
  // has a content_id -- that's the only case a click can open a real post's
  // real comments in the ContentDrawer.
  const isContentRows = !isFollowers && !isGap && !isDistribution;

  return (
    <div className="rounded-xl border p-4" style={accentStyle}>
      <div className="mb-3 text-sm font-semibold" style={{ color }}>{personName}</div>

      {loading && <div className="text-sm text-dark/50 dark:text-silver/50">Loading...</div>}
      {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}

      {data && (
        <div className="space-y-4">
          <div className="rounded-lg border border-silver/60 bg-white p-3 dark:border-navy-700 dark:bg-navy-900">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-dark/40 dark:text-silver/40">Formula</div>
            <p className="mt-1 text-xs text-dark dark:text-silver">{data.formula}</p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <Field label="Result" value={typeof data.value === "string" ? data.value : fmtNum(data.value, 2)} highlight />
            {data.period_days !== undefined && <Field label="Period (days)" value={fmtNum(data.period_days)} />}
            {data.count !== undefined && <Field label={isGap ? "Gaps Counted" : "Posts Counted"} value={fmtNum(data.count)} />}
            {data.sum !== undefined && data.sum !== null && <Field label="Sum" value={fmtNum(data.sum)} />}
            {data.followers !== undefined && <Field label="Followers Used" value={fmtNum(data.followers)} />}
            {data.average_engagement !== undefined && (
              <Field label="Avg Engagement" value={fmtNum(data.average_engagement, 2)} />
            )}
            {data.metric === "engagement_rate" && typeof data.value === "number" && (
              <Field label="As Shown" value={fmtPct(data.value)} />
            )}
          </div>

          <div>
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-dark/40 dark:text-silver/40">
              {recordsLabel} {!isFollowers && !isDistribution && `(${data.records.length})`}
              {isContentRows && data.records.length > 0 && (
                <span className="ml-2 normal-case font-normal text-dark/40 dark:text-silver/40">— click a post to read its real comments</span>
              )}
            </div>
            {data.records.length > 0 ? (
              <DataTable
                columns={columns} rows={data.records} keyFn={keyFn}
                onRowClick={isContentRows ? (r) => onOpenContent(r.content_id) : undefined}
                defaultSortKey={sortHighlightKey(request.metric)}
                minWidthClass={isDistribution ? "min-w-[220px]" : isGap ? "min-w-[480px]" : undefined}
              />
            ) : (
              <div className="rounded-md border border-dashed border-silver p-3 text-center text-xs text-dark/40 dark:border-navy-600 dark:text-silver/40">
                No underlying {emptyLabel} in the current filter window.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** The "followers" metric's records are profile-snapshot rows (run_id/
 * followers/finished_at), not content rows -- a completely different
 * shape from every other metric, so it gets its own column set
 * (content_id doesn't exist on it at all). Column set otherwise depends
 * only on the metric, not on which person -- computed once per panel. */
function columnsForMetric(metric: string): Column<any>[] {
  if (metric === "followers") {
    return [
      { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span>, sortable: true },
      { key: "followers", header: "Followers", render: (r) => fmtNum(r.followers), align: "right", sortable: true },
      { key: "followers_raw", header: "As Scraped", render: (r) => r.followers_raw ?? "—" },
      { key: "finished_at", header: "Scraped At", render: (r) => fmtDate(r.finished_at), sortable: true },
      { key: "run_id", header: "Run", render: (r) => r.run_id },
    ];
  }

  if (GAP_METRICS.has(metric)) {
    const gapKey = metric === "longest_inactive_period_days" ? "gap_days" : "gap_hours";
    const gapLabel = metric === "longest_inactive_period_days" ? "Gap (days)" : "Gap (hours)";
    return [
      { key: "from_content_id", header: "From Post", render: (r) => r.from_content_id, sortable: true },
      { key: "from_date", header: "From Date", render: (r) => fmtDate(r.from_date), sortable: true },
      { key: "to_content_id", header: "To Post", render: (r) => r.to_content_id, sortable: true },
      { key: "to_date", header: "To Date", render: (r) => fmtDate(r.to_date), sortable: true },
      { key: gapKey, header: gapLabel, render: (r) => fmtNum(r[gapKey], 2), align: "right", sortable: true },
    ];
  }

  if (DISTRIBUTION_METRICS.has(metric)) {
    return [
      { key: "label", header: metric === "most_active_day" ? "Day" : "Hour", render: (r) => r.label, sortable: true },
      { key: "count", header: "Posts", render: (r) => fmtNum(r.count), align: "right", sortable: true },
    ];
  }

  return [
    { key: "content_id", header: "Post", render: (r) => (
      r.content_url ? (
        // stopPropagation: the row itself is clickable (opens real comments
        // in ContentDrawer) -- without this, clicking the external-link
        // icon would open the original post AND the drawer at once.
        <a href={r.content_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-navy hover:underline">
          {r.content_id} <ExternalLink size={11} />
        </a>
      ) : r.content_id
    ) },
    { key: "content_type", header: "Type", render: (r) => <span className="capitalize">{r.content_type}</span>, sortable: true },
    { key: "published_at", header: "Date", render: (r) => fmtDate(r.published_at), sortable: true },
    { key: "likes", header: "Likes", render: (r) => fmtNum(r.likes), align: "right", sortable: true },
    { key: "comments_count", header: "Comments", render: (r) => fmtNum(r.comments_count), align: "right", sortable: true },
    // Only present on average_engagement/engagement_rate's own records
    // (see proof.py) -- shown only for those, not as a column of dashes
    // on metrics it doesn't apply to.
    ...(metric === "average_engagement" || metric === "total_engagement" || metric === "engagement_rate"
      ? [{ key: "engagement", header: "Engagement", render: (r: any) => fmtNum(r.engagement), align: "right" as const, sortable: true }]
      : []),
    ...(metric === "view_engagement"
      ? [{ key: "view_count", header: "Views", render: (r: any) => fmtNum(r.view_count), align: "right" as const, sortable: true }]
      : []),
  ];
}

/** Which column DataTable should render as initially highlighted --
 * matches the records' own server-side sort (proof.py's `_rows(...,
 * sort_by=...)`), so it never names a column this metric's records don't
 * actually have. */
function sortHighlightKey(metric: string): string | undefined {
  if (metric === "average_engagement" || metric === "total_engagement" || metric === "engagement_rate") return "engagement";
  if (metric === "average_likes" || metric === "median_likes" || metric === "total_likes") return "likes";
  if (metric === "average_comments" || metric === "total_comments_count") return "comments_count";
  if (metric === "view_engagement") return "view_count";
  if (metric === "longest_inactive_period_days") return "gap_days";
  if (metric === "median_interval_hours") return "gap_hours";
  if (DISTRIBUTION_METRICS.has(metric)) return "count";
  return undefined;
}

function Field({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-dark/40 dark:text-silver/40">{label}</div>
      <div className={`mt-0.5 font-semibold ${highlight ? "text-lg text-navy dark:text-white" : "text-dark dark:text-silver"}`}>{value}</div>
    </div>
  );
}
