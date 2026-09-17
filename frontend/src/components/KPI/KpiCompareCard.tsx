import type { LucideIcon } from "lucide-react";
import { Search } from "lucide-react";

/** The core "Person A vs Person B" KPI tile used throughout Overview/
 * Comparison (spec section 11). Always shows both raw values; "N/A" is
 * rendered by the caller via utils/format, never invented here.
 *
 * When `onProof` is given, the whole card is one click target that opens
 * both people's calculation evidence together (ProofDrawer) -- not a
 * separate link per side; a KPI is one number to verify, not two. */
export function KpiCompareCard({
  label,
  valueA,
  valueB,
  labelA,
  labelB,
  sublabel,
  icon: Icon,
  onProof,
}: {
  label: string;
  valueA: string;
  valueB: string;
  labelA: string;
  labelB: string;
  sublabel?: string;
  icon?: LucideIcon;
  onProof?: () => void;
}) {
  return (
    <div
      role={onProof ? "button" : undefined}
      tabIndex={onProof ? 0 : undefined}
      onClick={onProof}
      onKeyDown={onProof ? (e) => (e.key === "Enter" || e.key === " ") && onProof() : undefined}
      className={`group rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-all duration-150 ease-smooth hover:-translate-y-0.5 hover:border-navy-100 hover:shadow-card-hover dark:border-navy-700 dark:bg-navy-900 dark:hover:border-navy-500 ${
        onProof ? "cursor-pointer" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold uppercase tracking-wide text-dark/50 dark:text-silver/50">{label}</div>
          {sublabel && <div className="truncate text-[11px] text-dark/40 dark:text-silver/40">{sublabel}</div>}
        </div>
        {Icon && (
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gold/15 text-gold-700 transition-colors duration-150 group-hover:bg-gold group-hover:text-navy-900">
            <Icon size={15} strokeWidth={2.25} />
          </div>
        )}
      </div>
      <div className="mt-2.5 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[11px] font-medium text-navy/70 dark:text-silver/70" title={labelA}>{labelA}</div>
          <div className="text-lg font-bold text-navy dark:text-white">{valueA}</div>
        </div>
        <div className="h-6 w-px shrink-0 bg-silver dark:bg-navy-600" />
        <div className="min-w-0 text-right">
          <div className="truncate text-[11px] font-medium text-gold-700 dark:text-gold-300" title={labelB}>{labelB}</div>
          <div className="text-lg font-bold text-dark dark:text-white">{valueB}</div>
        </div>
      </div>
      {onProof && (
        <div className="mt-2.5 flex items-center justify-center gap-1 border-t border-silver/40 pt-2 text-[10px] font-medium text-dark/40 transition-colors group-hover:text-navy dark:border-navy-700 dark:text-silver/40 dark:group-hover:text-gold-300">
          <Search size={10} /> View calculation
        </div>
      )}
    </div>
  );
}
