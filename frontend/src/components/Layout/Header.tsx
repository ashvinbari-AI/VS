import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { useFilters } from "../../state/FilterContext";
import type { PersonConfig } from "../../types/api";

const PERIODS = [
  { label: "1 Day", days: 1 },
  { label: "7 Days", days: 7 },
  { label: "30 Days", days: 30 },
  { label: "90 Days", days: 90 },
];

export function Header() {
  const { filters, setFilters, refresh, people } = useFilters();
  const [spinning, setSpinning] = useState(false);

  const onRefresh = () => {
    setSpinning(true);
    refresh();
    window.setTimeout(() => setSpinning(false), 500);
  };

  return (
    <header className="sticky top-0 z-10 border-b border-silver/70 bg-white/90 px-6 py-3 backdrop-blur-md dark:border-navy-700/70 dark:bg-navy-900/90">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-dark/40 dark:text-silver/50">
            Political Person Comparison
          </div>
          <div className="flex items-center gap-2 text-sm font-bold text-navy dark:text-white">
            <PersonSelect
              value={filters.personA}
              onChange={(v) => setFilters({ personA: v })}
              people={people ?? []}
              placeholder="Select Person A"
            />
            <span className="rounded-full bg-silver/50 px-2 py-0.5 text-[10px] font-bold text-dark/40 dark:bg-navy-700/60 dark:text-silver/60">VS</span>
            <PersonSelect
              value={filters.personB}
              onChange={(v) => setFilters({ personB: v })}
              people={people ?? []}
              placeholder="Select Person B"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <FilterSelect value={filters.periodDays} onChange={(v) => setFilters({ periodDays: Number(v) })}>
            {PERIODS.map((p) => (
              <option key={p.days} value={p.days}>
                Last {p.label}
              </option>
            ))}
          </FilterSelect>

          <FilterSelect value={filters.platform} onChange={(v) => setFilters({ platform: v as any })}>
            <option value="all">All Platforms</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
          </FilterSelect>

          <FilterSelect value={filters.contentType} onChange={(v) => setFilters({ contentType: v as any })}>
            <option value="all">All Content</option>
            <option value="post">Posts</option>
            <option value="reel">Reels</option>
            <option value="video">Videos</option>
            <option value="photo">Photos</option>
          </FilterSelect>

          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 rounded-lg bg-gold px-3.5 py-1.5 text-xs font-bold text-navy-900 shadow-card transition-all duration-150 ease-smooth hover:-translate-y-0.5 hover:shadow-card-hover active:translate-y-0"
          >
            <RefreshCw size={13} className={spinning ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      </div>
    </header>
  );
}

function FilterSelect({
  value, onChange, children,
}: { value: string | number; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <select
      className="rounded-lg border border-silver bg-white px-2.5 py-1.5 text-xs font-medium text-dark/80 shadow-sm transition-colors hover:border-navy-300 focus:border-navy-400 dark:border-navy-600 dark:bg-navy-800 dark:text-silver dark:hover:border-navy-400"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {children}
    </select>
  );
}

function PersonSelect({
  value, onChange, people, placeholder,
}: { value: string; onChange: (v: string) => void; people: PersonConfig[]; placeholder: string }) {
  return (
    <select
      className="max-w-[180px] truncate rounded-lg border border-silver bg-white px-2 py-1 text-sm font-semibold text-navy shadow-sm transition-colors hover:border-navy-300 focus:border-navy-400 dark:border-navy-600 dark:bg-navy-800 dark:text-white dark:hover:border-navy-400"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {people.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
