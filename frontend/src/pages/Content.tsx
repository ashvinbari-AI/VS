import { useState } from "react";
import { ContentDrawer } from "../components/ContentDrawer/ContentDrawer";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { DataTable } from "../components/Tables/DataTable";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDate, fmtNum } from "../utils/format";
import type { ContentItem } from "../types/api";

export default function Content() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;
  const [selected, setSelected] = useState<string | null>(null);

  const { data, loading, error, reload } = useApi<{ items: ContentItem[] }>(
    () => api.get("/content", {
      person_ids: [filters.personA, filters.personB], platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
      sort_by: "engagement", sort_dir: "desc", page_size: 50,
    }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  const distribution = distributionByType(data?.items ?? [], filters.personA, filters.personB);

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      <div className="space-y-6">
        <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
          <h3 className="mb-3 text-sm font-semibold text-dark">Content Type Distribution</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-dark/50">
                <th className="py-1">Type</th><th className="py-1 text-right">{personAName} %</th><th className="py-1 text-right">{personBName} %</th>
              </tr>
            </thead>
            <tbody>
              {distribution.map((row) => (
                <tr key={row.type} className="border-t border-silver/30">
                  <td className="py-1.5 capitalize">{row.type}</td>
                  <td className="py-1.5 text-right">{row.aPct}%</td>
                  <td className="py-1.5 text-right">{row.bPct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-dark">Top Content (by Engagement)</h3>
          <DataTable
            rows={data?.items ?? []}
            keyFn={(r) => r.content_id}
            onRowClick={(r) => setSelected(r.content_id)}
            defaultSortKey="engagement"
            columns={[
              { key: "person", header: "Person", render: (r) => r.person_name, sortable: true, sortValue: (r) => r.person_name },
              { key: "platform", header: "Platform", render: (r) => <span className="capitalize">{r.platform}</span>, sortable: true, sortValue: (r) => r.platform },
              { key: "type", header: "Type", render: (r) => <span className="capitalize">{r.content_type}</span>, sortable: true, sortValue: (r) => r.content_type },
              { key: "date", header: "Date", render: (r) => fmtDate(r.published_at), sortable: true, sortValue: (r) => r.published_at },
              { key: "caption", header: "Caption", render: (r) => <span className="line-clamp-1 max-w-xs">{r.caption || "N/A"}</span> },
              { key: "likes", header: "Likes", render: (r) => fmtNum(r.likes), align: "right", sortable: true, sortValue: (r) => r.likes },
              { key: "comments", header: "Comments", render: (r) => fmtNum(r.comments_count), align: "right", sortable: true, sortValue: (r) => r.comments_count },
              { key: "engagement", header: "Engagement", render: (r) => fmtNum(r.engagement), align: "right", sortable: true, sortValue: (r) => r.engagement },
              { key: "narrative", header: "Narrative", render: (r) => r.narrative ?? "—", sortable: true, sortValue: (r) => r.narrative },
              { key: "sentiment", header: "Sentiment", render: (r) => r.sentiment ?? "—", sortable: true, sortValue: (r) => r.sentiment },
            ]}
          />
        </div>
      </div>
      <ContentDrawer contentId={selected} onClose={() => setSelected(null)} />
    </AsyncBoundary>
  );
}

function distributionByType(items: ContentItem[], personA: string, personB: string) {
  const types = ["post", "reel", "video", "photo"];
  const aItems = items.filter((i) => i.person_id === personA);
  const bItems = items.filter((i) => i.person_id === personB);
  return types.map((type) => ({
    type,
    aPct: aItems.length ? Math.round((aItems.filter((i) => i.content_type === type).length / aItems.length) * 100) : 0,
    bPct: bItems.length ? Math.round((bItems.filter((i) => i.content_type === type).length / bItems.length) * 100) : 0,
  }));
}
