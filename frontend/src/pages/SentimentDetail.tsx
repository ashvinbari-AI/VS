import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { ContentDrawer } from "../components/ContentDrawer/ContentDrawer";
import { DataTable } from "../components/Tables/DataTable";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { exportCsv, exportJson } from "../utils/exportData";
import { fmtDate, fmtDateTime, fmtNum } from "../utils/format";

const SENTIMENT_BADGE: Record<string, string> = {
  Positive: "bg-emerald-100 text-emerald-700",
  Negative: "bg-red-100 text-red-700",
  Neutral: "bg-slate-100 text-slate-600",
  "Mixed/Unclear": "bg-amber-100 text-amber-700",
};

function SentimentBadge({ label }: { label?: string | null }) {
  if (!label) return <span className="text-dark/30">—</span>;
  const cls = SENTIMENT_BADGE[label] ?? "bg-silver/40 text-dark/60";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

/** Drilldown behind a sentiment donut slice (Sentiment.tsx) -- opened in its
 * own tab so a reviewer can read the actual post captions / comment text a
 * label was assigned to, not just trust the aggregate count. Reads its
 * filters entirely from the URL (not FilterContext) since it's meant to be
 * openable standalone in a new tab. */
export default function SentimentDetail() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const personId = params.get("person") ?? "";
  const personName = params.get("name") || personId;
  const kind = params.get("kind") === "comment" ? "comment" : "post";
  const label = params.get("label") ?? "";
  const platform = params.get("platform") || undefined;
  const contentType = params.get("contentType") || undefined;
  const dateFrom = params.get("dateFrom") || undefined;
  const dateTo = params.get("dateTo") || undefined;

  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const ready = !!personId && !!label;

  // The Sentiment page embedded the comparison it was showing when this
  // slice was clicked (Sentiment.tsx's DonutCard) -- carry it straight
  // through so going back lands on the same Person A/B + filters, not a
  // blank page.
  const goBack = () => {
    const restore = new URLSearchParams();
    for (const key of ["restorePersonA", "restorePersonB", "restorePlatform", "restoreContentType", "restoreDateFrom", "restoreDateTo"]) {
      const value = params.get(key);
      if (value) restore.set(key, value);
    }
    const qs = restore.toString();
    navigate(`/sentiment${qs ? `?${qs}` : ""}`);
  };

  const { data, loading, error, reload } = useApi<{ items: any[]; total: number; total_pages: number }>(
    () =>
      kind === "post"
        ? api.get("/content", {
            person_ids: [personId], platform, content_type: contentType,
            date_from: dateFrom, date_to: dateTo, sentiment: label,
            sort_by: "published_at", sort_dir: "desc", page, page_size: 25,
          })
        : api.get("/comments/list", {
            person_id: personId, platform, date_from: dateFrom, date_to: dateTo,
            sentiment: label, page, page_size: 25,
          }),
    [personId, kind, label, platform, contentType, dateFrom, dateTo, page],
    ready
  );

  if (!ready) {
    return <p className="text-sm text-dark/50">Missing person/sentiment -- open this page from a sentiment chart slice.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-start gap-3">
          <button
            onClick={goBack}
            title="Back to Sentiment"
            className="mt-0.5 flex items-center gap-1 rounded-md border border-silver/80 px-2.5 py-1.5 text-xs font-medium text-dark hover:bg-silver/10"
          >
            <ArrowLeft size={14} /> Back
          </button>
          <div>
            <h1 className="text-lg font-semibold text-dark">
              {kind === "post" ? "Post" : "Comment"} Sentiment: <SentimentBadge label={label} /> <span className="ml-1">-- {personName}</span>
            </h1>
            <p className="text-xs text-dark/50">
              Model-classified sentiment -- not verified ground truth. Read the text below to cross-check the "{label}" label.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => exportCsv(`sentiment_${kind}_${label}.csv`, data?.items ?? [])}
            className="rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10"
          >
            Export CSV
          </button>
          <button
            onClick={() => exportJson(`sentiment_${kind}_${label}.json`, data?.items ?? [])}
            className="rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10"
          >
            Export JSON
          </button>
        </div>
      </div>

      <AsyncBoundary loading={loading} error={error} onRetry={reload}>
        {kind === "post" ? (
          <DataTable
            rows={data?.items ?? []}
            keyFn={(r) => r.content_id}
            onRowClick={(r) => setSelected(r.content_id)}
            columns={[
              { key: "date", header: "Date", render: (r) => fmtDate(r.published_at) },
              { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span> },
              { key: "type", header: "Type", render: (r) => <span className="capitalize">{r.content_type}</span> },
              { key: "caption", header: "Caption", render: (r) => <span className="whitespace-pre-wrap">{r.caption || "N/A"}</span> },
              { key: "likes", header: "Likes", render: (r) => fmtNum(r.likes), align: "right" },
              { key: "comments", header: "Comments", render: (r) => fmtNum(r.comments_count), align: "right" },
              { key: "sentiment", header: "Sentiment", render: (r) => <SentimentBadge label={r.sentiment} /> },
            ]}
          />
        ) : (
          <DataTable
            rows={data?.items ?? []}
            keyFn={(r) => r.comment_id}
            columns={[
              { key: "date", header: "Date", render: (r) => fmtDateTime(r.commented_at) },
              { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span> },
              { key: "author", header: "Author", render: (r) => r.author_username ?? "—" },
              { key: "text", header: "Comment", render: (r) => <span className="whitespace-pre-wrap">{r.comment_text}</span> },
              { key: "likes", header: "Likes", render: (r) => fmtNum(r.like_count), align: "right" },
              { key: "theme", header: "Theme", render: (r) => r.theme ?? "—" },
              { key: "sentiment", header: "Sentiment", render: (r) => <SentimentBadge label={r.sentiment} /> },
            ]}
          />
        )}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-2 text-sm">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-silver px-3 py-1 disabled:opacity-40">Previous</button>
            <span className="text-dark/50">Page {page} of {data.total_pages} ({data.total} results)</span>
            <button disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-silver px-3 py-1 disabled:opacity-40">Next</button>
          </div>
        )}
      </AsyncBoundary>
      {kind === "post" && <ContentDrawer contentId={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
