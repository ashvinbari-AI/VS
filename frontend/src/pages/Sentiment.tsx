import { useEffect, useRef } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useSearchParams } from "react-router-dom";
import { COLOR_PRIMARY } from "../utils/theme";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { comparisonDeps, comparisonParams, useFilters } from "../state/FilterContext";
import type { GlobalFilters } from "../types/api";

const SENTIMENT_COLORS: Record<string, string> = {
  Positive: "#0f9d58", Neutral: "#94A3B8", Negative: "#d93025", "Mixed/Unclear": "#F5A623",
};

export default function SentimentPage() {
  const { filters, setFilters, selected, ready } = useFilters();
  const [searchParams, setSearchParams] = useSearchParams();
  const restored = useRef(false);

  // Restores the exact person/platform/date selection that was active when
  // a donut slice was clicked open in another tab -- the back arrow on
  // /sentiment/detail lands here with that snapshot in the URL so this page
  // never comes back blank (no people selected again) after drilling in.
  useEffect(() => {
    if (restored.current) return;
    const rPeople = searchParams.get("restorePersonIds");
    if (!rPeople) return;
    restored.current = true;
    setFilters({
      personIds: rPeople.split(",").filter(Boolean),
      platform: (searchParams.get("restorePlatform") as typeof filters.platform) ?? filters.platform,
      contentType: (searchParams.get("restoreContentType") as typeof filters.contentType) ?? filters.contentType,
      dateFrom: searchParams.get("restoreDateFrom") ?? filters.dateFrom,
      dateTo: searchParams.get("restoreDateTo") ?? filters.dateTo,
    });
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/sentiment", comparisonParams(filters)),
    comparisonDeps(filters),
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && !data.analysis_available && (
        <EmptyState title="Sentiment analysis not run yet" message='Click "Run Analysis" on the Data Sources page to classify comment sentiment.' />
      )}
      {data && data.analysis_available && (
        <div className="space-y-6">
          <div className="rounded-md border border-navy/20 bg-navy/5 px-4 py-2 text-xs text-navy">
            {data.label} -- an AI/model-based classification, not verified ground truth.
          </div>
          <p className="text-[11px] text-dark/40">
            The day filter above applies by each comment's parent post's publish date -- comments themselves
            have no reliable timestamp in the scraped data, so a comment on an older post won't appear even if
            it was posted recently.
          </p>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {selected.map((p) => (
              <DonutCard key={p.id} title={`Comment Sentiment -- ${p.name}`} dist={data.comment_sentiment[p.id]}
                personId={p.id} personName={p.name} filters={filters} />
            ))}
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}

function DonutCard({
  title, dist, personId, personName, filters,
}: {
  title: string;
  dist: Record<string, number>;
  personId?: string;
  personName?: string;
  filters: GlobalFilters;
}) {
  const entries = Object.entries(dist || {});

  const openDetail = (label: string) => {
    if (!personId) return;
    const params = new URLSearchParams({ person: personId, name: personName ?? "", label });
    // Comments have no reliable timestamp of their own, so both this donut
    // (/api/sentiment) and the drilldown (/api/comments/list) filter
    // platform/content_type/date via the comment's *parent post* instead
    // (filter_comments_by_post, backend/app/analytics/filters.py) -- passing
    // the same filters through here keeps the drilldown's count matching
    // the slice that was clicked.
    if (filters.platform) params.set("platform", filters.platform);
    if (filters.contentType) params.set("contentType", filters.contentType);
    if (filters.dateFrom) params.set("dateFrom", filters.dateFrom);
    if (filters.dateTo) params.set("dateTo", filters.dateTo);
    // A full snapshot of the comparison in view when this slice was
    // clicked -- the back arrow on the detail page uses this to restore
    // /sentiment exactly as it was, instead of coming back to blank
    // people pickers (this opens in a new tab with its own fresh
    // FilterContext, which starts with nothing selected).
    params.set("restorePersonIds", filters.personIds.join(","));
    if (filters.platform) params.set("restorePlatform", filters.platform);
    if (filters.contentType) params.set("restoreContentType", filters.contentType);
    if (filters.dateFrom) params.set("restoreDateFrom", filters.dateFrom);
    if (filters.dateTo) params.set("restoreDateTo", filters.dateTo);
    window.open(`/sentiment/detail?${params.toString()}`, "_blank", "noopener");
  };

  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-xs text-dark/40">No data.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={entries.map(([name, value]) => ({ name, value }))}
                dataKey="value" nameKey="name" innerRadius={50} outerRadius={80}
                cursor="pointer"
                onClick={(entry: any) => openDetail(entry.name)}
              >
                {entries.map(([name]) => (
                  <Cell key={name} fill={SENTIMENT_COLORS[name] ?? COLOR_PRIMARY} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
          <p className="mt-1 text-center text-[11px] text-dark/40">Click a slice to open the underlying comments in a new tab.</p>
        </>
      )}
    </div>
  );
}
