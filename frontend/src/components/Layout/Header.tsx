import { Plus, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { useLocation } from "react-router-dom";
import { routeMeta } from "./navigation";
import { MAX_PEOPLE, useFilters } from "../../state/FilterContext";
import type { PersonConfig } from "../../types/api";

const PERIODS = [
  { label: "1 Day", days: 1 },
  { label: "7 Days", days: 7 },
  { label: "15 Days", days: 15 },
  { label: "30 Days", days: 30 },
  { label: "90 Days", days: 90 },
];

export function Header() {
  const { filters, setFilters, refresh } = useFilters();
  const [spinning, setSpinning] = useState(false);
  const { pathname } = useLocation();
  const meta = routeMeta(pathname);
  const showComparison = meta?.comparison ?? false;

  const onRefresh = () => {
    setSpinning(true);
    refresh();
    window.setTimeout(() => setSpinning(false), 500);
  };

  return (
    <header className="sticky top-0 z-10 border-b border-silver/70 bg-white/95 backdrop-blur-md dark:border-navy-700/70 dark:bg-navy-900/95">
      {/* Row 1 -- where am I? */}
      <div className="flex items-center justify-between gap-4 px-6 pb-2 pt-4">
        <div className="min-w-0">
          {meta && (
            <div className="text-[11px] font-semibold uppercase tracking-wide text-dark/40 dark:text-silver/50">{meta.group}</div>
          )}
          <h1 className="truncate text-xl font-bold text-navy dark:text-white">{meta?.label ?? "Political Intelligence"}</h1>
          {meta && <p className="truncate text-xs text-dark/55 dark:text-silver/55">{meta.description}</p>}
        </div>
        <button
          onClick={onRefresh}
          title="Reload the data on this page"
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-gold px-3.5 py-2 text-xs font-bold text-navy-900 shadow-card transition-all duration-150 ease-smooth hover:-translate-y-0.5 hover:shadow-card-hover active:translate-y-0"
        >
          <RefreshCw size={13} className={spinning ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {showComparison && (
        <div className="space-y-2 px-6 pb-3 pt-1">
          {/* Row 2 -- who am I comparing? */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <RowLabel>Comparing</RowLabel>
            <PeoplePicker />
          </div>

          {/* Row 3 -- over what slice of data? */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <RowLabel>Filters</RowLabel>
            <LabeledFilter label="Period">
              <FilterSelect value={filters.periodDays} onChange={(v) => setFilters({ periodDays: Number(v) })}>
                {PERIODS.map((p) => (
                  <option key={p.days} value={p.days}>
                    Last {p.label}
                  </option>
                ))}
              </FilterSelect>
            </LabeledFilter>
            <LabeledFilter label="Platform">
              <FilterSelect value={filters.platform} onChange={(v) => setFilters({ platform: v as any })}>
                <option value="all">All Platforms</option>
                <option value="instagram">Instagram</option>
                <option value="facebook">Facebook</option>
              </FilterSelect>
            </LabeledFilter>
            <LabeledFilter label="Content">
              <FilterSelect value={filters.contentType} onChange={(v) => setFilters({ contentType: v as any })}>
                <option value="all">All Content</option>
                <option value="post">Posts</option>
                <option value="reel">Reels</option>
                <option value="video">Videos</option>
                <option value="photo">Photos</option>
              </FilterSelect>
            </LabeledFilter>
            {(filters.platform !== "all" || filters.contentType !== "all") && (
              <button
                type="button"
                onClick={() => setFilters({ platform: "all", contentType: "all" })}
                className="text-xs font-medium text-navy/70 underline-offset-2 hover:text-navy hover:underline dark:text-silver/70 dark:hover:text-white"
              >
                Reset filters
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

function RowLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="w-20 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-dark/40 dark:text-silver/50">
      {children}
    </span>
  );
}

function LabeledFilter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-dark/50 dark:text-silver/50">
      {label}
      {children}
    </label>
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

/** Selected people as removable chips ("A VS B VS C ..."), each one a
 * dropdown to swap that slot for someone else, plus an "Add person" picker
 * until MAX_PEOPLE are selected. A slot's position decides its chart color. */
function PeoplePicker() {
  const { filters, setFilters, people, selected, peopleError, peopleLoading } = useFilters();
  const ids = filters.personIds;

  const replaceAt = (slot: number, id: string) => {
    const next = [...ids];
    if (id) next[slot] = id;
    else next.splice(slot, 1);
    setFilters({ personIds: next });
  };
  const removeAt = (slot: number) => setFilters({ personIds: ids.filter((_, i) => i !== slot) });
  const add = (id: string) => id && setFilters({ personIds: [...ids, id] });

  // A person already picked in another slot isn't offered again.
  const availableFor = (currentId: string | null) =>
    people.filter((p) => p.id === currentId || !ids.includes(p.id));

  const unpicked = availableFor(null);

  if (peopleError) {
    return <span className="text-xs font-medium text-red-600 dark:text-red-400">Can't load people -- is the backend running?</span>;
  }
  if (peopleLoading) {
    return <span className="text-xs text-dark/40 dark:text-silver/40">Loading people...</span>;
  }
  if (people.length === 0) {
    return <span className="text-xs text-dark/50 dark:text-silver/50">No people yet -- add them under Data Sources.</span>;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-sm font-bold text-navy dark:text-white">
      {selected.map((person, slot) => (
        <div key={person.id} className="flex items-center gap-1.5">
          {slot > 0 && (
            <span className="rounded-full bg-silver/50 px-2 py-0.5 text-[10px] font-bold text-dark/40 dark:bg-navy-700/60 dark:text-silver/60">VS</span>
          )}
          <div
            className="flex items-center gap-1 rounded-lg border bg-white pl-2 shadow-sm dark:bg-navy-800"
            style={{ borderColor: person.color }}
          >
            <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: person.color }} />
            <PersonSelect
              value={person.id}
              onChange={(v) => replaceAt(slot, v)}
              people={availableFor(person.id)}
            />
            <button
              type="button"
              onClick={() => removeAt(slot)}
              title={`Remove ${person.name}`}
              className="rounded-r-lg px-1.5 py-1 text-dark/40 hover:bg-silver/30 hover:text-dark dark:text-silver/50 dark:hover:bg-navy-700"
            >
              <X size={12} />
            </button>
          </div>
        </div>
      ))}

      {ids.length < MAX_PEOPLE && unpicked.length > 0 && (
        <div className="flex items-center gap-1.5">
          {ids.length > 0 && (
            <span className="rounded-full bg-silver/50 px-2 py-0.5 text-[10px] font-bold text-dark/40 dark:bg-navy-700/60 dark:text-silver/60">VS</span>
          )}
          <label className="flex items-center gap-1 rounded-lg border border-dashed border-silver bg-white pl-2 text-dark/50 shadow-sm hover:border-navy-300 dark:border-navy-600 dark:bg-navy-800 dark:text-silver/60">
            <Plus size={12} />
            <select
              className="max-w-[170px] truncate rounded-lg bg-transparent py-1 pr-2 text-sm font-semibold text-dark/60 focus:outline-none dark:text-silver/70"
              value=""
              onChange={(e) => add(e.target.value)}
            >
              <option value="">{ids.length === 0 ? "Select a person" : "Add person"}</option>
              {unpicked.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
        </div>
      )}
    </div>
  );
}

function PersonSelect({
  value, onChange, people,
}: { value: string; onChange: (v: string) => void; people: PersonConfig[] }) {
  return (
    <select
      className="max-w-[170px] truncate bg-transparent py-1 text-sm font-semibold text-navy focus:outline-none dark:text-white"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {people.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
