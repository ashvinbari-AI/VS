import { AlertTriangle } from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { KpiCompareCard } from "../components/KPI/KpiCompareCard";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtCompact, fmtNum, fmtPct } from "../utils/format";

export default function Engagement() {
  const { filters, personAName, personBName } = useFilters();
  const ready = !!filters.personA && !!filters.personB;
  const { data, loading, error, reload } = useApi<any>(
    () => api.get("/engagement", {
      person_a: filters.personA, person_b: filters.personB, platform: filters.platform,
      content_type: filters.contentType, date_from: filters.dateFrom, date_to: filters.dateTo,
    }),
    [filters.personA, filters.personB, filters.platform, filters.contentType, filters.dateFrom],
    ready
  );

  if (!ready) return <SelectPeoplePrompt />;

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="space-y-6">
          {(!data.person_a.data_quality.shares_available || !data.person_b.data_quality.shares_available) && (
            <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
              <AlertTriangle size={14} />
              Shares are not available for one or both people (not provided by the source platform's scraper output). Shown as N/A rather than 0.
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCompareCard label="Average Engagement" valueA={fmtCompact(data.person_a.average_engagement)} valueB={fmtCompact(data.person_b.average_engagement)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Median Engagement" valueA={fmtCompact(data.person_a.median_engagement)} valueB={fmtCompact(data.person_b.median_engagement)} labelA={personAName} labelB={personBName} sublabel="Resistant to viral outliers" />
            <KpiCompareCard label="Engagement Rate" valueA={fmtPct(data.person_a.engagement_rate_pct)} valueB={fmtPct(data.person_b.engagement_rate_pct)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Per 1,000 Followers" valueA={fmtNum(data.person_a.engagement_per_1000_followers)} valueB={fmtNum(data.person_b.engagement_per_1000_followers)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Average Likes" valueA={fmtCompact(data.person_a.average_likes)} valueB={fmtCompact(data.person_b.average_likes)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Median Likes" valueA={fmtCompact(data.person_a.median_likes)} valueB={fmtCompact(data.person_b.median_likes)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Average Comments" valueA={fmtCompact(data.person_a.average_comments)} valueB={fmtCompact(data.person_b.average_comments)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Median Comments" valueA={fmtCompact(data.person_a.median_comments)} valueB={fmtCompact(data.person_b.median_comments)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard
              label="Average Shares"
              valueA={data.person_a.data_quality.shares_available ? fmtCompact(data.person_a.average_shares) : "N/A — not provided by source"}
              valueB={data.person_b.data_quality.shares_available ? fmtCompact(data.person_b.average_shares) : "N/A — not provided by source"}
              labelA={personAName} labelB={personBName}
            />
            <KpiCompareCard label="P90 Engagement" valueA={fmtCompact(data.person_a.p90_engagement)} valueB={fmtCompact(data.person_b.p90_engagement)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="P95 Engagement" valueA={fmtCompact(data.person_a.p95_engagement)} valueB={fmtCompact(data.person_b.p95_engagement)} labelA={personAName} labelB={personBName} />
            <KpiCompareCard label="Top 10% Avg Engagement" valueA={fmtCompact(data.person_a.top10_percent_avg_engagement)} valueB={fmtCompact(data.person_b.top10_percent_avg_engagement)} labelA={personAName} labelB={personBName} />
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}
