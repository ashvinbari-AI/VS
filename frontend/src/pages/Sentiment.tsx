import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
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
  const { filters, personAName, personBName } = useFilters();
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
            <DonutCard title={`Post Sentiment -- ${personAName}`} dist={data.post_sentiment.person_a} />
            <DonutCard title={`Post Sentiment -- ${personBName}`} dist={data.post_sentiment.person_b} />
            <DonutCard title={`Comment Sentiment -- ${personAName}`} dist={data.comment_sentiment.person_a} />
            <DonutCard title={`Comment Sentiment -- ${personBName}`} dist={data.comment_sentiment.person_b} />
          </div>
        </div>
      )}
    </AsyncBoundary>
  );
}

function DonutCard({ title, dist }: { title: string; dist: Record<string, number> }) {
  const entries = Object.entries(dist || {});
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-2 text-sm font-semibold text-dark">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-xs text-dark/40">No data.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={entries.map(([name, value]) => ({ name, value }))} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80}>
              {entries.map(([name]) => (
                <Cell key={name} fill={SENTIMENT_COLORS[name] ?? COLOR_PRIMARY} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
