import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** Shared chart panel shell -- rounded card, title row, optional icon badge
 * and header action slot (e.g. a legend toggle or "Check Now" CTA). Used
 * across Overview/Activity/etc. so every chart panel looks consistent. */
export function ChartCard({
  title,
  icon: Icon,
  action,
  children,
}: {
  title: string;
  icon?: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover dark:border-navy-700 dark:bg-navy-900">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-dark dark:text-white">
          {Icon && (
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-navy-50 text-navy dark:bg-navy-700 dark:text-gold-300">
              <Icon size={13} strokeWidth={2.25} />
            </span>
          )}
          {title}
        </h3>
        {action}
      </div>
      {children}
    </div>
  );
}
