import { createContext, ReactNode, useContext, useMemo, useState } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import type { GlobalFilters, PersonConfig } from "../types/api";

interface FilterContextValue {
  filters: GlobalFilters;
  setFilters: (patch: Partial<GlobalFilters>) => void;
  refreshKey: number;
  refresh: () => void;
  /** All configured people (fetched once here so every page/component can
   * resolve a name without its own /profiles round-trip). */
  people: PersonConfig[];
  /** The selected people's real names -- falls back to "Person A"/"Person B"
   * only while nothing is picked yet or the list hasn't loaded. Use these
   * instead of hardcoding "Person A"/"Person B" anywhere in the UI. */
  personAName: string;
  personBName: string;
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const DEFAULT_FILTERS: GlobalFilters = {
  personA: "",
  personB: "",
  platform: "all",
  contentType: "all",
  dateFrom: daysAgoIso(1),
  dateTo: null,
  periodDays: 1,
};

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFiltersState] = useState<GlobalFilters>(DEFAULT_FILTERS);
  const [refreshKey, setRefreshKey] = useState(0);
  const { data: peopleData } = useApi(() => api.get<PersonConfig[]>("/profiles"), []);
  const people = peopleData ?? [];

  const personAName = people.find((p) => p.id === filters.personA)?.name ?? "Person A";
  const personBName = people.find((p) => p.id === filters.personB)?.name ?? "Person B";

  const value = useMemo<FilterContextValue>(
    () => ({
      filters,
      setFilters: (patch) =>
        setFiltersState((prev) => {
          const next = { ...prev, ...patch };
          if (patch.periodDays !== undefined) {
            next.dateFrom = daysAgoIso(patch.periodDays);
            next.dateTo = null;
          }
          return next;
        }),
      refreshKey,
      refresh: () => setRefreshKey((k) => k + 1),
      people,
      personAName,
      personBName,
    }),
    [filters, refreshKey, people, personAName, personBName]
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used within FilterProvider");
  return ctx;
}
