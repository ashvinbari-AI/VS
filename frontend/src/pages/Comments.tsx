import { useState } from "react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDateTime, fmtNum } from "../utils/format";

export default function Comments() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;
  const [issue, setIssue] = useState<string | null>(null);

  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/comments", { person_a: filters.personA, person_b: filters.personB, platform: filters.platform }),
    [filters.personA, filters.personB, filters.platform],
    ready
  );
  const { data: drilldown } = useApi<any>(
    () => api.get(`/comments/issues/${encodeURIComponent(issue!)}`, { person_a: filters.personA, person_b: filters.personB }),
    [issue, filters.personA, filters.personB],
    !!issue
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && !data.analysis_available && (
        <EmptyState title="Comment analysis not run yet" message='Click "Run Analysis" on the Data Sources page to classify comment themes and detect public issues.' />
      )}
      {data && data.analysis_available && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PersonCommentBlock title={personAName} block={data.person_a} onSelectIssue={setIssue} />
            <PersonCommentBlock title={personBName} block={data.person_b} onSelectIssue={setIssue} />
          </div>

          {issue && (
            <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
              <h3 className="mb-2 text-sm font-semibold text-dark">Issue Drilldown: {issue}</h3>
              <div className="max-h-80 space-y-2 overflow-y-auto">
                {(drilldown?.items ?? []).map((item: any, idx: number) => (
                  <div key={idx} className="rounded-md border border-silver/40 p-2 text-xs">
                    <div className="flex justify-between text-dark/50">
                      <span>{item.person_name} · {item.platform}</span>
                      <span>{fmtDateTime(item.commented_at)}</span>
                    </div>
                    <div className="mt-1">{item.comment_text}</div>
                    {item.sentiment && <div className="mt-1 text-[10px] text-dark/40">Sentiment: {item.sentiment}</div>}
                  </div>
                ))}
                {drilldown && drilldown.items.length === 0 && <p className="text-xs text-dark/40">No matching comments.</p>}
              </div>
            </div>
          )}
        </div>
      )}
    </AsyncBoundary>
  );
}

function PersonCommentBlock({ title, block, onSelectIssue }: { title: string; block: any; onSelectIssue: (i: string) => void }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
        <h3 className="mb-2 text-sm font-semibold text-dark">{title} -- Comment Stats</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div><div className="text-[11px] text-dark/40">Total Comments</div><div className="font-semibold">{fmtNum(block.total_comments)}</div></div>
          <div><div className="text-[11px] text-dark/40">Avg / Post</div><div className="font-semibold">{fmtNum(block.average_comments_per_post, 1)}</div></div>
          <div><div className="text-[11px] text-dark/40">Median / Post</div><div className="font-semibold">{fmtNum(block.median_comments_per_post)}</div></div>
        </div>
      </div>

      <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
        <h3 className="mb-2 text-sm font-semibold text-dark">Theme Breakdown</h3>
        {Object.entries(block.theme_breakdown ?? {}).map(([theme, count]) => (
          <div key={theme} className="flex justify-between border-t border-silver/20 py-1 text-sm first:border-0">
            <span>{theme}</span><span className="font-medium">{fmtNum(count as number)}</span>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
        <h3 className="mb-2 text-sm font-semibold text-dark">Public Issues Mentioned</h3>
        {(block.issues ?? []).map((row: any) => (
          <button
            key={row.issue}
            onClick={() => onSelectIssue(row.issue)}
            className="flex w-full justify-between border-t border-silver/20 py-1.5 text-left text-sm hover:bg-navy/5 first:border-0"
          >
            <span>{row.issue}</span>
            <span className="font-medium">{row.mentions} ({row.percentage}%)</span>
          </button>
        ))}
        {(block.issues ?? []).length === 0 && <p className="text-xs text-dark/40">No explicit issue mentions detected.</p>}
      </div>
    </div>
  );
}
