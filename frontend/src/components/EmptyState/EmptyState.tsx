import { Inbox } from "lucide-react";
import { ReactNode } from "react";

export function EmptyState({ title, message, icon }: { title: string; message: string; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-silver bg-white/60 py-16 text-center dark:border-navy-600 dark:bg-navy-900/60">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-50 text-navy-400 dark:bg-navy-800 dark:text-navy-300">
        {icon ?? <Inbox size={28} />}
      </div>
      <div className="text-sm font-semibold text-dark dark:text-white">{title}</div>
      <div className="mt-1 max-w-md text-sm text-dark/60 dark:text-silver/60">{message}</div>
    </div>
  );
}
