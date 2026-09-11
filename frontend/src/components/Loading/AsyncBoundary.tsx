import { ReactNode } from "react";
import { ErrorState } from "../ErrorState/ErrorState";
import { CardSkeleton } from "./Skeleton";

/** Wraps a page's body with the standard loading/error handling so every
 * page renders these states consistently (spec section 38). */
export function AsyncBoundary({
  loading,
  error,
  onRetry,
  children,
}: {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  children: ReactNode;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }
  return <>{children}</>;
}
