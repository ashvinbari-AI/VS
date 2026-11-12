import type { ReactNode } from "react";

/** A titled block within a page ("Key numbers", "Trends", ...), so long
 * pages read as clear sections instead of one undivided wall of cards. */
export function Section({
  title, description, action, children,
}: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2 border-b border-silver/60 pb-2 dark:border-navy-700">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wide text-navy-700 dark:text-silver">{title}</h2>
          {description && <p className="text-xs text-dark/50 dark:text-silver/50">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
