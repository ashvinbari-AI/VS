import { useCallback, useEffect, useRef, useState } from "react";

interface State<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Generic "fetch on mount / when deps change" hook used by every page.
 * `fetcher` should be a stable-enough closure -- pages pass an inline
 * function and list their real dependencies in `deps`. Returns `reload()`
 * to re-run the same fetch on demand (e.g. the header's Refresh button). */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[], enabled = true): State<T> & { reload: () => void } {
  const [state, setState] = useState<State<T>>({ data: null, loading: enabled, error: null });
  const [tick, setTick] = useState(0);
  const counter = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const my = ++counter.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetcher()
      .then((data) => {
        if (!cancelled && my === counter.current) setState({ data, loading: false, error: null });
      })
      .catch((err: Error) => {
        if (!cancelled && my === counter.current) setState({ data: null, loading: false, error: err.message });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, tick, ...deps]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
