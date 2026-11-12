import { useState } from "react";
import { ChevronsLeft, ChevronsRight, Shield } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useApi } from "../../hooks/useApi";
import { api } from "../../services/api";
import { NAV_GROUPS } from "./navigation";

const COLLAPSE_KEY = "sidebar-collapsed";

export function Sidebar() {
  const { data: health } = useApi(() => api.get<any>("/health"), []);
  // Collapsed = icons only, for more chart room on smaller screens.
  // Remembered across reloads.
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const toggle = () => {
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      return !c;
    });
  };

  const geminiOn = !!health?.nlp_mode?.startsWith("GEMINI NLP ENABLED");

  return (
    <aside
      className={`flex h-screen shrink-0 flex-col bg-gradient-to-b from-navy-700 to-navy-900 text-white shadow-nav transition-[width] duration-200 ${
        collapsed ? "w-[68px]" : "w-60"
      }`}
    >
      <div className={`flex items-center gap-3 py-5 ${collapsed ? "justify-center px-2" : "px-5"}`}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gold shadow-card">
          <Shield size={18} className="text-navy-900" strokeWidth={2.25} />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-sm font-bold leading-tight">Political Intelligence</div>
            <div className="text-[11px] text-white/45">Social media comparison</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mt-3 first:mt-0">
            {collapsed ? (
              <div className="mx-2 mb-2 h-px bg-white/10" />
            ) : (
              <div className="mb-1 px-3 text-[10px] font-bold uppercase tracking-wider text-white/35">{group.title}</div>
            )}
            <div className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  title={collapsed ? label : undefined}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg py-2 text-sm transition-all duration-150 ease-smooth ${
                      collapsed ? "justify-center px-0" : "px-3"
                    } ${
                      isActive
                        ? "bg-gold font-semibold text-navy-900 shadow-card"
                        : "text-white/70 hover:bg-white/[0.07] hover:text-white"
                    }`
                  }
                >
                  <Icon size={16} strokeWidth={2.1} className="shrink-0" />
                  {!collapsed && <span className="truncate">{label}</span>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 px-3 py-3">
        {!collapsed && (
          <div className="mb-2 px-2 text-[11px] text-white/60">
            <StatusLine label="Running locally" ok />
            <StatusLine label={geminiOn ? "Gemini NLP on" : "Local NLP (Gemini off)"} ok={geminiOn} />
            {health?.demo_mode && (
              <div className="mt-1.5 inline-flex items-center rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-gold-300">
                Demo Mode
              </div>
            )}
          </div>
        )}
        <button
          type="button"
          onClick={toggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`flex w-full items-center gap-2 rounded-lg py-1.5 text-xs text-white/50 hover:bg-white/[0.07] hover:text-white ${
            collapsed ? "justify-center" : "px-2"
          }`}
        >
          {collapsed ? <ChevronsRight size={15} /> : <><ChevronsLeft size={15} /> Collapse</>}
        </button>
      </div>
    </aside>
  );
}

function StatusLine({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-1.5 py-0.5">
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]" : "bg-white/25"}`} />
      {label}
    </div>
  );
}
