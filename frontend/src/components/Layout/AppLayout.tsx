import { Suspense, useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { api } from "../../services/api";
import { setDateFormat } from "../../utils/dateFormat";
import { applyTheme } from "../../utils/themeStore";
import { CardSkeleton } from "../Loading/Skeleton";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

function RouteFallback() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

export function AppLayout() {
  const location = useLocation();

  // Load the saved date format once per app session -- fmtDate/fmtDateTime
  // (utils/format.ts) read it from the utils/dateFormat.ts singleton, not
  // from React state, since they're called as plain functions from many
  // pages, not as hooks.
  useEffect(() => {
    api.get<{ date_format: string; theme: string }>("/settings")
      .then((s) => { setDateFormat(s.date_format); applyTheme(s.theme); })
      .catch(() => {});
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-offwhite dark:bg-navy-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <div key={location.pathname} className="page-enter">
            <Suspense fallback={<RouteFallback />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}
