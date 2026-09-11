export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`skeleton-shimmer rounded ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card space-y-3">
      <div className="flex items-start justify-between gap-2">
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="h-7 w-2/3" />
    </div>
  );
}
