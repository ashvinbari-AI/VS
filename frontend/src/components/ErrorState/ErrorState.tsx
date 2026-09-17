import { AlertTriangle } from "lucide-react";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50 py-12 text-center dark:border-red-900/60 dark:bg-red-950/40">
      <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-red-500 dark:bg-red-900/60 dark:text-red-400">
        <AlertTriangle size={22} />
      </div>
      <div className="text-sm font-medium text-red-700 dark:text-red-300">Something went wrong</div>
      <div className="mt-1 max-w-md text-sm text-red-600 dark:text-red-300/80">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-lg border border-red-300 bg-white px-3.5 py-1.5 text-sm font-medium text-red-700 shadow-sm transition-all duration-150 ease-smooth hover:-translate-y-0.5 hover:bg-red-100 hover:shadow-card dark:border-red-800 dark:bg-navy-900 dark:text-red-300 dark:hover:bg-red-950/60"
        >
          Retry
        </button>
      )}
    </div>
  );
}
