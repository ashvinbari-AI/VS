import { Inbox } from "lucide-react";
import { ReactNode } from "react";

export function EmptyState({ title, message, icon }: { title: string; message: string; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-silver bg-white/60 py-16 text-center">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-50 text-navy-400">
        {icon ?? <Inbox size={28} />}
      </div>
      <div className="text-sm font-semibold text-dark">{title}</div>
      <div className="mt-1 max-w-md text-sm text-dark/60">{message}</div>
    </div>
  );
}
