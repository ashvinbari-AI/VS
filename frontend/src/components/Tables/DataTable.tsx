import { ReactNode, useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortable?: boolean;
  align?: "left" | "right" | "center";
}

/** Generic client-side sortable table for already-fetched pages of data
 * (server does the actual pagination/filtering -- spec section 46). */
export function DataTable<T>({
  columns,
  rows,
  keyFn,
  onRowClick,
  defaultSortKey,
}: {
  columns: Column<T>[];
  rows: T[];
  keyFn: (row: T) => string;
  onRowClick?: (row: T) => void;
  defaultSortKey?: string;
}) {
  const [sortKey, setSortKey] = useState<string | undefined>(defaultSortKey);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => rows, [rows]);

  return (
    <div className="overflow-x-auto rounded-xl border border-silver/60 bg-white shadow-card">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-silver/60 bg-navy-50/60 text-left text-xs font-semibold uppercase tracking-wide text-navy-700/70">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2.5 ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"} ${col.sortable ? "cursor-pointer select-none transition-colors hover:text-gold-700" : ""}`}
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
              <td colSpan={columns.length} className="px-3 py-8 text-center text-sm text-dark/40">
                No rows match the current filters.
              </td>
            </tr>
          )}
          {sorted.map((row) => (
            <tr
              key={keyFn(row)}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-silver/30 transition-colors last:border-0 ${onRowClick ? "cursor-pointer hover:bg-gold/5" : "hover:bg-navy-50/40"}`}
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
