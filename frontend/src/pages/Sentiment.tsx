import { useEffect, useRef } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useSearchParams } from "react-router-dom";
import { COLOR_PRIMARY } from "../utils/theme";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";

const SENTIMENT_COLORS: Record<string, string> = {
  Positive: "#0f9d58", Neutral: "#94A3B8", Negative: "#d93025", "Mixed/Unclear": "#F5A623",
};

export default function SentimentPage() {
  const { filters, setFilters, personAName, personBName } = useFilters();
  const [searchParams, setSearchParams] = useSearchParams();
  const restored = useRef(false);

  // Restores the exact person/platform/date selection that was active when
  // a donut slice was clicked open in another tab -- the back arrow on
  // /sentiment/detail lands here with that snapshot in the URL so this page
  // never comes back blank ("Select Person A/B" again) after drilling in.
  useEffect(() => {
    if (restored.current) return;
    const rPersonA = searchParams.get("restorePersonA");
    const rPersonB = searchParams.get("restorePersonB");
    if (!rPersonA && !rPersonB) return;
    restored.current = true;
    setFilters({
      personA: rPersonA ?? filters.personA,
      personB: rPersonB ?? filters.personB,
      platform: (searchParams.get("restorePlatform") as typeof filters.platform) ?? filters.platform,
      contentType: (searchParams.get("restoreContentType") as typeof filters.contentType) ?? filters.contentType,
      dateFrom: searchParams.get("restoreDateFrom") ?? filters.dateFrom,
      dateTo: searchParams.get("restoreDateTo") ?? filters.dateTo,
    });
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const ready = !!filters.personA && !!filters.personB;
  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/sentiment", {
      person_a: filters.personA, person_b: filters.personB, platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
    }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && !data.analysis_available && (
        <EmptyState title="Sentiment analysis not run yet" message='Click "Run Analysis" on the Data Sources page to classify post/comment sentiment.' />
      )}
      {data && data.analysis_available && (
        <div className="space-y-6">
          <div className="rounded-md border border-navy/20 bg-navy/5 px-4 py-2 text-xs text-navy">
            {data.label} -- an AI/model-based classification, not verified ground truth.
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <DonutCard title={`Post Sentiment -- ${personAName}`} dist={data.post_sentiment.person_a}
              kind="post" personId={filters.personA} personName={personAName} filters={filters} />
            <DonutCard title={`Post Sentiment -- ${personBName}`} dist={data.post_sentiment.person_b}
              kind="post" personId={filters.personB} personName={personBName} filters={filters} />
            <DonutCard title={`Comment Sentiment -- ${personAName}`} dist={data.comment_sentiment.person_a}
              kind="comment" personId={filters.personA} personName={personAName} filters={filters} />
            <DonutCard title={`Comment Sentiment -- ${personBName}`} dist={data.comment_sentiment.person_b}
              kind="comment" personId={filters.personB} personName={personBName} filters={filters} />
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}

function DonutCard({
  title, dist, kind, personId, personName, filters,
}: {
  title: string;
  dist: Record<string, number>;
  kind: "post" | "comment";
  personId?: string;
  personName?: string;
  filters: { personA: string; personB: string; platform?: string; contentType?: string; dateFrom?: string | null; dateTo?: string | null };
}) {
  const entries = Object.entries(dist || {});

  const openDetail = (label: string) => {
    if (!personId) return;
    const params = new URLSearchParams({ person: personId, name: personName ?? "", kind, label });
    // Comment-sentiment counts here come from /api/sentiment, which (like
    // /api/comments) only filters comments by person -- most comment rows
    // have no reliable timestamp, so platform/date aren't applied to them.
    // Passing those through here would just make the drilldown mismatch
    // the count on the slice a person clicked.
    if (kind === "post") {
      if (filters.platform) params.set("platform", filters.platform);
      if (filters.contentType) params.set("contentType", filters.contentType);
      if (filters.dateFrom) params.set("dateFrom", filters.dateFrom);
      if (filters.dateTo) params.set("dateTo", filters.dateTo);
    }
    // A full snapshot of the comparison in view when this slice was
    // clicked -- the back arrow on the detail page uses this to restore
    // /sentiment exactly as it was, instead of coming back to blank
    // Person A/B pickers (this opens in a new tab with its own fresh
    // FilterContext, which starts with nothing selected).
    params.set("restorePersonA", filters.personA);
    params.set("restorePersonB", filters.personB);
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
          <p className="mt-1 text-center text-[11px] text-dark/40">Click a slice to open the underlying {kind}s in a new tab.</p>
        </>
      )}
    </div>
  );
}
