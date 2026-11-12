import { createContext, ReactNode, useContext, useMemo, useState } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import type { GlobalFilters, PersonConfig } from "../types/api";
import { personColor } from "../utils/theme";

/** Most people one comparison can include. Matches MAX_COMPARE_PEOPLE in
 * backend/app/routers/people_params.py -- keep both in sync. */
export const MAX_PEOPLE = 6;
/** Fewest people a comparison page needs before it fetches anything. */
export const MIN_PEOPLE = 2;

/** One selected person, resolved for display: real name + their slot color. */
export interface SelectedPerson {
  id: string;
  name: string;
  color: string;
}

interface FilterContextValue {
  filters: GlobalFilters;
  setFilters: (patch: Partial<GlobalFilters>) => void;
  refreshKey: number;
  refresh: () => void;
  /** All configured people (fetched once here so every page/component can
   * resolve a name without its own /profiles round-trip). */
  people: PersonConfig[];
  /** True until the people list has loaded at least once. */
  peopleLoading: boolean;
  /** Set when the people list couldn't be fetched (e.g. backend down) --
   * so the UI can say so instead of claiming nobody has been added. */
  peopleError: string | null;
  /** The selected people in comparison order, with real names and colors.
   * Use these instead of hardcoding names/colors anywhere in the UI. */
  selected: SelectedPerson[];
  /** True once at least MIN_PEOPLE people are selected. */
  ready: boolean;
  nameFor: (personId: string) => string;
  colorFor: (personId: string) => string;
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const DEFAULT_FILTERS: GlobalFilters = {
  personIds: [],
  platform: "all",
  contentType: "all",
  dateFrom: daysAgoIso(1),
  dateTo: null,
  periodDays: 1,
};

/** The query params every comparison endpoint shares. */
export function comparisonParams(filters: GlobalFilters): Record<string, unknown> {
  return {
    person_ids: filters.personIds,
    platform: filters.platform,
    content_type: filters.contentType,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  };
}

/** A stable useApi dependency list for the shared comparison filters
 * (personIds joined so a new-but-equal array doesn't refetch). */
export function comparisonDeps(filters: GlobalFilters): unknown[] {
  return [filters.personIds.join(","), filters.platform, filters.contentType, filters.dateFrom, filters.dateTo];
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFiltersState] = useState<GlobalFilters>(DEFAULT_FILTERS);
  const [refreshKey, setRefreshKey] = useState(0);
  // Refetched on refresh() so adding/deleting a person updates the pickers.
  const { data: peopleData, loading: peopleLoading, error: peopleError } =
    useApi(() => api.get<PersonConfig[]>("/profiles"), [refreshKey]);
  const people = peopleData ?? [];

  const selected = useMemo<SelectedPerson[]>(
    () =>
      filters.personIds.map((id, slot) => ({
        id,
        name: people.find((p) => p.id === id)?.name ?? `Person ${slot + 1}`,
        color: personColor(slot),
      })),
    [filters.personIds, people]
  );

  const value = useMemo<FilterContextValue>(
    () => ({
      filters,
      setFilters: (patch) =>
        setFiltersState((prev) => {
          const next = { ...prev, ...patch };
          if (patch.personIds !== undefined) {
            // De-dupe, drop blanks, cap at MAX_PEOPLE.
            next.personIds = Array.from(new Set(patch.personIds.filter(Boolean))).slice(0, MAX_PEOPLE);
          }
          if (patch.periodDays !== undefined) {
            next.dateFrom = daysAgoIso(patch.periodDays);
            next.dateTo = null;
          }
          return next;
        }),
      refreshKey,
      refresh: () => setRefreshKey((k) => k + 1),
      people,
      peopleLoading: peopleLoading && !peopleData,
      peopleError,
      selected,
      ready: selected.length >= MIN_PEOPLE,
      nameFor: (id) => selected.find((p) => p.id === id)?.name ?? people.find((p) => p.id === id)?.name ?? id,
      colorFor: (id) => selected.find((p) => p.id === id)?.color ?? personColor(0),
    }),
    [filters, refreshKey, people, peopleData, peopleLoading, peopleError, selected]
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used within FilterProvider");
  return ctx;
}
