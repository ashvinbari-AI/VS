import {
  Activity, BarChart3, Users, MessageSquare, FileText, Compass,
  Clock, Database, Settings as SettingsIcon, TrendingUp, Smile, Search, Shield, ClipboardCheck,
  FileBarChart,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useApi } from "../../hooks/useApi";
import { api } from "../../services/api";

const NAV = [
  { to: "/overview", label: "Overview", icon: BarChart3 },
  { to: "/report", label: "Report", icon: FileBarChart },
  { to: "/comparison", label: "Profile Comparison", icon: Users },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/engagement", label: "Engagement", icon: TrendingUp },
  { to: "/content", label: "Content", icon: FileText },
  { to: "/narratives", label: "Narratives", icon: Compass },
  { to: "/sentiment", label: "Sentiment", icon: Smile },
  { to: "/comments", label: "Comments", icon: MessageSquare },
  { to: "/timeline", label: "Timeline", icon: Clock },
  { to: "/explorer", label: "Content Explorer", icon: Search },
  { to: "/data-sources", label: "Data Sources", icon: Database },
  { to: "/evaluation", label: "Evaluation", icon: ClipboardCheck },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export function Sidebar() {
  const { data: health } = useApi(() => api.get<any>("/health"), []);

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-gradient-to-b from-navy-700 to-navy-900 text-white shadow-nav">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gold shadow-card">
          <Shield size={20} className="text-navy-900" strokeWidth={2.25} />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-bold leading-tight">Political Intelligence</div>
          <div className="text-[11px] text-white/45">Local-only platform</div>
        </div>
      </div>

      <div className="mx-4 mb-1 h-px bg-white/10" />

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150 ease-smooth ${
                isActive
                  ? "bg-gold text-navy-900 font-semibold shadow-card"
                  : "text-white/70 hover:bg-white/[0.07] hover:text-white hover:translate-x-0.5"
              }`
            }
          >
            <Icon size={16} strokeWidth={2.1} />
            <span className="truncate">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mx-4 mb-1 h-px bg-white/10" />

      <div className="px-5 py-4 text-[11px] text-white/60">
        <div className="mb-1.5 font-semibold uppercase tracking-wide text-white/35">System Status</div>
        <StatusLine label="Local" ok />
        <StatusLine label="Data Loaded" ok={!!health?.demo_mode || health !== undefined} />
        <StatusLine
          label={health?.nlp_mode?.startsWith("GEMINI NLP ENABLED") ? "Gemini: Comment Sentiment" : "Gemini: Disabled"}
          ok={!!health?.nlp_mode?.startsWith("GEMINI NLP ENABLED")}
        />
        {health?.demo_mode && (
          <div className="mt-2 inline-flex items-center rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-gold-300">
            Demo Mode
          </div>
        )}
      </div>
    </aside>
  );
}

function StatusLine({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-1.5 py-0.5">
      <span className={`h-1.5 w-1.5 rounded-full transition-colors ${ok ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]" : "bg-white/25"}`} />
      {label}
    </div>
  );
}
