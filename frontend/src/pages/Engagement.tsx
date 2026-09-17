import { ExternalLink, Image as ImageIcon, Trophy, Video } from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { SelectPeoplePrompt } from "../components/EmptyState/SelectPeoplePrompt";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useFilters } from "../state/FilterContext";
import { fmtDate, fmtNum } from "../utils/format";
import { COLOR_PRIMARY, COLOR_SECONDARY } from "../utils/theme";

interface TopContentItem {
  content_id: string;
  person_id: string;
  person_name: string;
  platform: string;
  content_type: string;
  published_at: string | null;
  likes: number | null;
  comments_count: number | null;
  engagement: number | null;
  content_url: string | null;
}

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

  const nameFor = (personId: string) => (personId === filters.personA ? personAName : personBName);
  const colorFor = (personId: string) => (personId === filters.personA ? COLOR_PRIMARY : COLOR_SECONDARY);

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="space-y-8">
          <TopContentSection
            title="Top Posts" icon={ImageIcon} items={data.top_posts} emptyLabel="posts"
            nameFor={nameFor} colorFor={colorFor}
          />
          <TopContentSection
            title="Top Reels" icon={Video} items={data.top_reels} emptyLabel="reels"
            nameFor={nameFor} colorFor={colorFor}
          />
        </div>
      )}
    </AsyncBoundary>
  );
}

function TopContentSection({
  title, icon: Icon, items, emptyLabel, nameFor, colorFor,
}: {
  title: string;
  icon: typeof ImageIcon;
  items: TopContentItem[];
  emptyLabel: string;
  nameFor: (personId: string) => string;
  colorFor: (personId: string) => string;
}) {
  return (
    <div>
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-dark dark:text-white">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-gold/15 text-gold-700">
          <Icon size={13} strokeWidth={2.25} />
        </span>
        {title}
      </h3>

      {(!items || items.length === 0) ? (
        <div className="rounded-xl border border-dashed border-silver p-6 text-center text-sm text-dark/40 dark:border-navy-600 dark:text-silver/40">
          No {emptyLabel} with engagement data in the current filter window.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {items.map((item, i) => (
            <RankCard key={item.content_id} rank={i + 1} item={item} name={nameFor(item.person_id)} color={colorFor(item.person_id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function RankCard({ rank, item, name, color }: { rank: number; item: TopContentItem; name: string; color: string }) {
  const Wrapper = item.content_url ? "a" : "div";
  const wrapperProps = item.content_url
    ? { href: item.content_url, target: "_blank", rel: "noreferrer" }
    : {};

  return (
    <Wrapper
      {...(wrapperProps as any)}
      className={`group block rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-all duration-150 ease-smooth dark:border-navy-700 dark:bg-navy-900 ${
        item.content_url ? "cursor-pointer hover:-translate-y-0.5 hover:border-navy-100 hover:shadow-card-hover dark:hover:border-navy-500" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
            style={{ backgroundColor: rank === 1 ? "#F5A623" : rank === 2 ? "#8B93A7" : "#C9971F" }}
          >
            #{rank}
          </span>
          <div className="min-w-0">
            <div className="truncate text-xs font-semibold" style={{ color }} title={name}>{name}</div>
            <div className="text-[11px] text-dark/40 dark:text-silver/40">{fmtDate(item.published_at)}</div>
          </div>
        </div>
        {item.content_url && (
          <ExternalLink size={13} className="mt-0.5 shrink-0 text-dark/30 transition-colors group-hover:text-navy dark:text-silver/40 dark:group-hover:text-gold-300" />
        )}
      </div>

      <div className="mt-3 text-2xl font-bold text-navy dark:text-white">{fmtNum(item.engagement)}</div>
      <div className="text-[11px] text-dark/40 dark:text-silver/40">engagement</div>

      <div className="mt-3 flex items-center gap-4 border-t border-silver/40 pt-2 text-xs text-dark/60 dark:border-navy-700 dark:text-silver/60">
        <span>Likes {fmtNum(item.likes)}</span>
        <span>Comments {fmtNum(item.comments_count)}</span>
      </div>
    </Wrapper>
  );
}
