import { CheckCircle2, X, XCircle } from "lucide-react";
import { createContext, ReactNode, useCallback, useContext, useState } from "react";

interface Toast {
  id: number;
  kind: "success" | "error" | "info";
  title: string;
  message?: string;
  action?: { label: string; onClick: () => void };
}

interface ToastContextValue {
  show: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Simple local toast/popup system -- no external dependency needed. Used
 * to surface "scraping finished" the moment a background job completes,
 * per spec section 6/48 ("show scraper progress"), rather than making the
 * user notice a status line changed. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((toast: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { ...toast, id }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 12000);
  }, []);

  const dismiss = (id: number) => setToasts((t) => t.filter((x) => x.id !== id));

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className="rounded-lg border border-silver/60 bg-white p-3 shadow-lg">
            <div className="flex items-start gap-2">
              {t.kind === "success" && <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-500" />}
              {t.kind === "error" && <XCircle size={18} className="mt-0.5 shrink-0 text-red-500" />}
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-dark">{t.title}</div>
                {t.message && <div className="mt-0.5 text-xs text-dark/60">{t.message}</div>}
                {t.action && (
                  <button
                    onClick={() => { t.action!.onClick(); dismiss(t.id); }}
                    className="mt-2 rounded-md bg-navy px-2.5 py-1 text-xs font-semibold text-white hover:bg-navy/90"
                  >
                    {t.action.label}
                  </button>
                )}
              </div>
              <button onClick={() => dismiss(t.id)} className="shrink-0 text-dark/30 hover:text-dark/60">
                <X size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
