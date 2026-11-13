import { useState } from "react";
import { ContentDrawer } from "../components/ContentDrawer/ContentDrawer";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { DataTable } from "../components/Tables/DataTable";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters, type SelectedPerson } from "../state/FilterContext";
import { fmtDate, fmtNum } from "../utils/format";
import type { ContentItem } from "../types/api";

export default function Content() {
  const { filters, selected: people, ready } = useFilters();
  const [selected, setSelected] = useState<string | null>(null);

  const { data, loading, error, reload } = useApi<{ items: ContentItem[] }>(
    () => api.get("/content", {
      person_ids: filters.personIds, platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
      sort_by: "engagement", sort_dir: "desc", page_size: 50,
    }),
    [filters.personIds.join(","), filters.platform, filters.contentType, filters.dateFrom],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  const distribution = distributionByType(data?.items ?? [], people);

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      <div className="space-y-6">
        <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
          <h3 className="mb-3 text-sm font-semibold text-dark">Content Type Distribution</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-dark/50">
                <th className="py-1">Type</th>
                {people.map((p) => (
                  <th key={p.id} className="py-1 text-right">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
                      {p.name} %
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {distribution.map((row) => (
                <tr key={row.type} className="border-t border-silver/30">
                  <td className="py-1.5 capitalize">{row.type}</td>
                  {people.map((p) => (
                    <td key={p.id} className="py-1.5 text-right">{row.pct[p.id]}%</td>
                  ))}
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
            ]}
          />
        </div>
      </div>
      <ContentDrawer contentId={selected} onClose={() => setSelected(null)} />
    </AsyncBoundary>
  );
}

function distributionByType(items: ContentItem[], people: SelectedPerson[]) {
  const types = ["post", "reel", "video", "photo"];
  const byPerson = Object.fromEntries(people.map((p) => [p.id, items.filter((i) => i.person_id === p.id)]));
  return types.map((type) => ({
    type,
    pct: Object.fromEntries(people.map((p) => {
      const own = byPerson[p.id];
      return [p.id, own.length ? Math.round((own.filter((i) => i.content_type === type).length / own.length) * 100) : 0];
    })) as Record<string, number>,
  }));
}
