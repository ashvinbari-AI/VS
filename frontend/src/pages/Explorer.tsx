import { Download, Search } from "lucide-react";
import { useState } from "react";
import { ContentDrawer } from "../components/ContentDrawer/ContentDrawer";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { DataTable } from "../components/Tables/DataTable";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDate, fmtNum } from "../utils/format";
import { exportCsv, exportJson } from "../utils/exportData";
import type { ContentItem } from "../types/api";

export default function Explorer() {
  const { filters } = useFilters();
  const [search, setSearch] = useState("");
  const [minLikes, setMinLikes] = useState<string>("");
  const [minComments, setMinComments] = useState<string>("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  const personIds = [filters.personA, filters.personB].filter(Boolean);

  const { data, loading, error, reload } = useApi<{ items: ContentItem[]; total: number; total_pages: number }>(
    () => api.get("/content", {
      person_ids: personIds.length ? personIds : undefined,
      platform: filters.platform, content_type: filters.contentType,
      date_from: filters.dateFrom, date_to: filters.dateTo,
      search: search || undefined,
      min_likes: minLikes || undefined, min_comments: minComments || undefined,
      sort_by: "published_at", sort_dir: "desc", page, page_size: 25,
    }),
    [filters.platform, filters.contentType, filters.dateFrom, search, minLikes, minComments, page, personIds.join(",")]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-silver/60 bg-white p-3 shadow-sm">
        <div className="flex flex-1 min-w-[220px] items-center gap-2 rounded-md border border-silver/70 px-2 py-1.5">
          <Search size={14} className="text-dark/40" />
          <input
            className="w-full text-sm outline-none"
            placeholder="Search caption, hashtag..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <input type="number" placeholder="Min likes" className="w-28 rounded-md border border-silver/70 px-2 py-1.5 text-sm"
          value={minLikes} onChange={(e) => { setMinLikes(e.target.value); setPage(1); }} />
        <input type="number" placeholder="Min comments" className="w-32 rounded-md border border-silver/70 px-2 py-1.5 text-sm"
          value={minComments} onChange={(e) => { setMinComments(e.target.value); setPage(1); }} />
        <button
          onClick={() => exportCsv("content_explorer.csv", data?.items ?? [])}
          className="flex items-center gap-1 rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10"
        >
          <Download size={13} /> CSV
        </button>
        <button
          onClick={() => exportJson("content_explorer.json", data?.items ?? [])}
          className="flex items-center gap-1 rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10"
        >
          <Download size={13} /> JSON
        </button>
      </div>

      <AsyncBoundary loading={loading} error={error} onRetry={reload}>
        <DataTable
          rows={data?.items ?? []}
          keyFn={(r) => r.content_id}
          onRowClick={(r) => setSelected(r.content_id)}
          columns={[
            { key: "date", header: "Date", render: (r) => fmtDate(r.published_at) },
            { key: "person", header: "Person", render: (r) => r.person_name },
            { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span> },
            { key: "type", header: "Type", render: (r) => <span className="capitalize">{r.content_type}</span> },
            { key: "caption", header: "Caption", render: (r) => <span className="line-clamp-1 max-w-sm">{r.caption || "N/A"}</span> },
            { key: "likes", header: "Likes", render: (r) => fmtNum(r.likes), align: "right" },
            { key: "comments", header: "Comments", render: (r) => fmtNum(r.comments_count), align: "right" },
            { key: "engagement", header: "Engagement", render: (r) => fmtNum(r.engagement), align: "right" },
            { key: "narrative", header: "Narrative", render: (r) => r.narrative ?? "—" },
            { key: "sentiment", header: "Sentiment", render: (r) => r.sentiment ?? "—" },
          ]}
        />
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-2 text-sm">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-silver px-3 py-1 disabled:opacity-40">Previous</button>
            <span className="text-dark/50">Page {page} of {data.total_pages} ({data.total} results)</span>
            <button disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-silver px-3 py-1 disabled:opacity-40">Next</button>
          </div>
        )}
      </AsyncBoundary>
      <ContentDrawer contentId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
