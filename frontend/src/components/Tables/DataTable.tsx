import { ReactNode, useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortable?: boolean;
  align?: "left" | "right" | "center";
  /** How to read this column's raw, comparable value off a row for
   * sorting -- `render` returns JSX, which isn't sortable. Falls back to
   * `(row as any)[key]` when omitted, which works whenever `key` happens
   * to match a real field name on the row. */
  sortValue?: (row: T) => string | number | null | undefined;
}

/** Generic client-side sortable table for already-fetched pages of data
 * (server does the actual pagination/filtering -- spec section 46).
 * Sorting is stable (equal/missing values keep their original relative
 * order) and always sorts missing values (null/undefined) to the end,
 * regardless of direction -- "N/A" never jumps to the top just because
 * descending sort treats it as the largest value. */
export function DataTable<T>({
  columns,
  rows,
  keyFn,
  onRowClick,
  defaultSortKey,
  minWidthClass = "min-w-[640px]",
}: {
  columns: Column<T>[];
  rows: T[];
  keyFn: (row: T) => string;
  onRowClick?: (row: T) => void;
  defaultSortKey?: string;
  /** Tables with only 2-3 short columns (e.g. ProofDrawer's day/hour
   * distributions) look forced and get needlessly horizontally cropped in
   * a narrow container at the default width tuned for 6+ wide content
   * tables -- pass a smaller class (or "" for none) for those. */
  minWidthClass?: string;
}) {
  const [sortKey, setSortKey] = useState<string | undefined>(defaultSortKey);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return rows;
    const getValue = col.sortValue ?? ((row: T) => (row as Record<string, unknown>)[col.key] as string | number | null | undefined);

    // Index-tagged so equal (or both-missing) values keep their original
    // relative order instead of Array.sort's unspecified tie-breaking.
    return rows
      .map((row, index) => ({ row, index, value: getValue(row) }))
      .sort((a, b) => {
        const aMissing = a.value === null || a.value === undefined || a.value === "";
        const bMissing = b.value === null || b.value === undefined || b.value === "";
        if (aMissing && bMissing) return a.index - b.index;
        if (aMissing) return 1;   // missing always last, both directions
        if (bMissing) return -1;
        let cmp: number;
        if (typeof a.value === "number" && typeof b.value === "number") {
          cmp = a.value - b.value;
        } else {
          cmp = String(a.value).localeCompare(String(b.value));
        }
        if (cmp === 0) cmp = a.index - b.index;
        return sortDir === "asc" ? cmp : -cmp;
      })
      .map((entry) => entry.row);
  }, [rows, columns, sortKey, sortDir]);

  return (
    <div className="overflow-x-auto rounded-xl border border-silver/60 bg-white shadow-card dark:border-navy-700 dark:bg-navy-900">
      <table className={`w-full ${minWidthClass} text-sm`}>
        <thead>
          <tr className="border-b border-silver/60 bg-navy-50/60 text-left text-xs font-semibold uppercase tracking-wide text-navy-700/70 dark:border-navy-700 dark:bg-navy-800/60 dark:text-silver/70">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2.5 ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"} ${col.sortable ? "cursor-pointer select-none transition-colors hover:text-gold-700 dark:hover:text-gold-300" : ""}`}
                onClick={() => {
                  if (!col.sortable) return;
                  if (sortKey === col.key) setSortDir(sortDir === "asc" ? "desc" : "asc");
                  else {
                    setSortKey(col.key);
                    setSortDir("desc");
                  }
                }}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && sortKey === col.key && (sortDir === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-sm text-dark/40 dark:text-silver/40">
                No rows match the current filters.
              </td>
            </tr>
          )}
          {sorted.map((row) => (
            <tr
              key={keyFn(row)}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-silver/30 transition-colors last:border-0 dark:border-navy-700/60 ${onRowClick ? "cursor-pointer hover:bg-gold/5 dark:hover:bg-gold/10" : "hover:bg-navy-50/40 dark:hover:bg-navy-800/40"}`}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-3 py-2.5 ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
