import { useState } from "react";
import { AlertTriangle, CheckCircle2, History, MinusCircle, PlayCircle, XCircle } from "lucide-react";
import { AsyncBoundary } from "../components/Loading/AsyncBoundary";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { fmtNum } from "../utils/format";

type Status = "PASS" | "WARNING" | "FAIL" | "NOT_EVALUATED";

interface ScorecardRow {
  category: "data" | "analytics" | "nlp";
  metric: string;
  label: string;
  value: number | null;
  status: Status;
}

interface RegressionEntry {
  baseline: number | null;
  current: number | null;
  diff: number | null;
  status: "REGRESSION" | "IMPROVED" | "STABLE" | "NOT_COMPARABLE";
}

interface EvaluationReport {
  run_id: string;
  generated_at: string;
  dataset_version: string;
  modules_run: string[];
  scorecard: ScorecardRow[];
  sample_sizes: { posts: number; comments: number; profiles: number };
  regression: { has_baseline: boolean; metrics?: Record<string, RegressionEntry>; note?: string };
  limitations: string[];
}

const CATEGORY_LABELS: Record<ScorecardRow["category"], string> = {
  data: "Data Quality", analytics: "Analytics", nlp: "NLP",
};

const MODULE_OPTIONS = [
  { value: "all", label: "All Modules" },
  { value: "scraper", label: "Scraper (Completeness / Field Accuracy / Duplicates)" },
  { value: "metrics", label: "Metrics (Engagement / Activity)" },
  { value: "nlp", label: "NLP (Sentiment / Narrative / Theme / Issues)" },
  { value: "comparison", label: "Comparison Engine" },
];

/** Consolidated single-page evaluation dashboard -- reads the independent
 * evaluation/ package's own report shape (evaluation/run.py::build_report)
 * via /api/evaluation/*. Grouped by category (data/analytics/nlp), never
 * blended into one overall score (spec section 30). */
export default function Evaluation() {
  const { data, loading, error, reload } = useApi<EvaluationReport>(() => api.get("/evaluation/overview"), []);
  const { data: history, reload: reloadHistory } = useApi<{ run_ids: string[] }>(() => api.get("/evaluation/reports"), []);
  const [moduleChoice, setModuleChoice] = useState("all");
  const [saveBaseline, setSaveBaseline] = useState(false);
  const [running, setRunning] = useState(false);
  const [viewing, setViewing] = useState<EvaluationReport | null>(null);

  const report = viewing ?? data;

  const runNow = async () => {
    setRunning(true);
    try {
      await api.post<EvaluationReport>("/evaluation/run", { module: moduleChoice, save_baseline: saveBaseline });
      setViewing(null);
      reload();
      reloadHistory();
    } finally {
      setRunning(false);
    }
  };

  const viewHistoricalRun = async (runId: string) => {
    const result = await api.get<EvaluationReport>(`/evaluation/reports/${runId}`);
    setViewing(result);
  };

  return (
    <AsyncBoundary loading={loading} error={error} onRetry={reload}>
      {report && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-silver/60 bg-white p-4 shadow-card">
            <div>
              <div className="text-sm font-semibold text-dark">
                {viewing ? `Viewing saved run: ${viewing.run_id}` : "Live Evaluation"}
              </div>
              <div className="text-xs text-dark/50">
                {fmtNum(report.sample_sizes.posts)} posts · {fmtNum(report.sample_sizes.comments)} comments ·{" "}
                {fmtNum(report.sample_sizes.profiles)} profile snapshots
              </div>
              {viewing && (
                <button onClick={() => setViewing(null)} className="mt-1 text-xs font-medium text-navy hover:underline">
                  ← Back to live overview
                </button>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={moduleChoice}
                onChange={(e) => setModuleChoice(e.target.value)}
                className="rounded-md border border-silver/70 px-2 py-1.5 text-xs"
              >
                {MODULE_OPTIONS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-xs text-dark/70">
                <input type="checkbox" checked={saveBaseline} onChange={(e) => setSaveBaseline(e.target.checked)} />
                Save as baseline
              </label>
              <button
                disabled={running}
                onClick={runNow}
                className="flex items-center gap-1 rounded-md bg-navy px-3 py-1.5 text-xs font-semibold text-white hover:bg-navy/90 disabled:opacity-50"
              >
                <PlayCircle size={13} /> {running ? "Running..." : "Run Evaluation"}
              </button>
            </div>
          </div>

          {(["data", "analytics", "nlp"] as const).map((cat) => (
            <ScorecardSection key={cat} label={CATEGORY_LABELS[cat]} rows={report.scorecard.filter((r) => r.category === cat)} />
          ))}

          <RegressionSection regression={report.regression} />

          {history && history.run_ids.length > 0 && (
            <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-dark">
                <History size={14} /> Run History
              </div>
              <div className="flex flex-wrap gap-2">
                {history.run_ids.map((id) => (
                  <button
                    key={id}
                    onClick={() => viewHistoricalRun(id)}
                    className={`rounded-full border px-2.5 py-1 text-xs ${
                      viewing?.run_id === id
                        ? "border-navy bg-navy/10 font-semibold text-navy"
                        : "border-silver/70 text-dark/60 hover:bg-silver/10"
                    }`}
                  >
                    {id}
                  </button>
                ))}
              </div>
            </div>
          )}

          {report.limitations?.length > 0 && (
            <div className="rounded-xl border border-dashed border-silver bg-offwhite/60 p-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-dark/50">Limitations</div>
              <ul className="space-y-1.5 text-xs text-dark/70">
                {report.limitations.map((l, i) => (
                  <li key={i}>• {l}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </AsyncBoundary>
  );
}

function ScorecardSection({ label, rows }: { label: string; rows: ScorecardRow[] }) {
  if (!rows.length) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-dark">{label}</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {rows.map((row) => (
          <MetricCard key={row.metric} row={row} />
        ))}
      </div>
    </div>
  );
}

function MetricCard({ row }: { row: ScorecardRow }) {
  const valueStr = row.value === null
    ? "N/A"
    : Math.abs(row.value) <= 1.5
      ? row.value.toFixed(3)
      : `${row.value.toFixed(1)}%`;
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <div className="text-xs font-medium text-dark/60">{row.label}</div>
      <div className="mt-1 text-2xl font-bold text-dark">{valueStr}</div>
      <StatusBadge status={row.status} />
    </div>
  );
}

const STATUS_CONFIG: Record<Status, { icon: typeof CheckCircle2; classes: string; label: string }> = {
  PASS: { icon: CheckCircle2, classes: "bg-emerald-100 text-emerald-700", label: "PASS" },
  WARNING: { icon: AlertTriangle, classes: "bg-amber-100 text-amber-700", label: "WARNING" },
  FAIL: { icon: XCircle, classes: "bg-red-100 text-red-700", label: "FAIL" },
  NOT_EVALUATED: { icon: MinusCircle, classes: "bg-silver/40 text-dark/50", label: "NOT EVALUATED" },
};

/** Status is always shown as an icon + text label together, never color
 * alone (spec section 59's accessibility rule). */
function StatusBadge({ status }: { status: Status }) {
  const c = STATUS_CONFIG[status] ?? STATUS_CONFIG.NOT_EVALUATED;
  const Icon = c.icon;
  return (
    <div className={`mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${c.classes}`}>
      <Icon size={11} /> {c.label}
    </div>
  );
}

function RegressionSection({ regression }: { regression: EvaluationReport["regression"] }) {
  if (!regression?.has_baseline) {
    return (
      <div className="rounded-xl border border-dashed border-silver bg-white/60 p-4 text-xs text-dark/50">
        No regression baseline saved yet — run evaluation with "Save as baseline" checked to start tracking
        regressions run over run.
      </div>
    );
  }
  const entries = Object.entries(regression.metrics ?? {});
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-dark">Regression vs. Baseline</h3>
      <div className="overflow-x-auto rounded-xl border border-silver/60 bg-white shadow-card">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-silver/60 bg-silver/10 text-left text-xs uppercase text-dark/50">
              <th className="px-3 py-2">Metric</th>
              <th className="px-3 py-2 text-right">Baseline</th>
              <th className="px-3 py-2 text-right">Current</th>
              <th className="px-3 py-2 text-right">Diff</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([name, r]) => (
              <tr key={name} className="border-t border-silver/30">
                <td className="px-3 py-2">{name}</td>
                <td className="px-3 py-2 text-right">{r.baseline ?? "N/A"}</td>
                <td className="px-3 py-2 text-right">{r.current ?? "N/A"}</td>
                <td className="px-3 py-2 text-right">{r.diff ?? "N/A"}</td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      r.status === "REGRESSION"
                        ? "bg-red-100 text-red-700"
                        : r.status === "IMPROVED"
                          ? "bg-emerald-100 text-emerald-700"
                          : r.status === "STABLE"
                            ? "bg-silver/40 text-dark/60"
                            : "bg-silver/20 text-dark/40"
                    }`}
                  >
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
