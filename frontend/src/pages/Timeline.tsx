import { useState } from "react";
import { ContentDrawer } from "../components/ContentDrawer/ContentDrawer";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDate, fmtDateTime, fmtNum } from "../utils/format";
import type { ContentItem } from "../types/api";

export default function Timeline() {
  const { filters } = useFilters();
  const ready = !!filters.personA && !!filters.personB;
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  const { data, loading, error, reload } = useApi<{ items: ContentItem[]; total: number; total_pages: number }>(
    () => api.get("/timeline", {
      person_ids: [filters.personA, filters.personB], platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
      page, page_size: 30,
    }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom, page],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  const grouped = groupByDate(data?.items ?? []);

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      <div className="space-y-6">
        {grouped.map(([date, items]) => (
          <div key={date}>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-dark/50">{fmtDate(date)}</div>
            <div className="space-y-2">
              {items.map((item) => (
                <button
                  key={item.content_id}
                  onClick={() => setSelected(item.content_id)}
                  className="flex w-full items-center justify-between rounded-lg border border-silver/60 bg-white px-4 py-2.5 text-left text-sm hover:border-navy/40"
                >
                  <div>
                    <span className="font-semibold text-navy">{item.person_name}</span>{" "}
                    <span className="capitalize text-dark/60">{item.platform} · {item.content_type}</span>
                    <div className="mt-0.5 line-clamp-1 max-w-lg text-xs text-dark/50">{item.caption || "N/A"}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-xs text-dark/50">
                    <span>{fmtDateTime(item.published_at_local || item.published_at).split(" ").slice(-2).join(" ")}</span>
                    <span>{fmtNum(item.engagement)} eng.</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}

        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-2 text-sm">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-silver px-3 py-1 disabled:opacity-40">Previous</button>
            <span className="text-dark/50">Page {page} of {data.total_pages}</span>
            <button disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-silver px-3 py-1 disabled:opacity-40">Next</button>
          </div>
        )}
      </div>
      <ContentDrawer contentId={selected} onClose={() => setSelected(null)} />
    </AsyncBoundary>
  );
}

function groupByDate(items: ContentItem[]): [string, ContentItem[]][] {
  const map = new Map<string, ContentItem[]>();
  for (const item of items) {
    const day = (item.published_at || "unknown").slice(0, 10);
    if (!map.has(day)) map.set(day, []);
    map.get(day)!.push(item);
  }
  return Array.from(map.entries()).sort((a, b) => (a[0] < b[0] ? 1 : -1));
}
