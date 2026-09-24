import { History, Pencil, PlayCircle, Plus, RefreshCw, UploadCloud, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/Toast/ToastProvider";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import type { PersonConfig } from "../types/api";
import { fmtDate, fmtDateTime, fmtNum } from "../utils/format";

interface DataSourceRow {
  person_id: string; person_name: string; platform: string; profile_url: string | null;
  last_scraped: string | null; content_count: number; comments_count: number;
  status: string; errors: string[];
  earliest_post: string | null; latest_post: string | null; days_of_content: number | null;
  scrape_window_since: string | null; scrape_window_until: string | null;
}

export default function DataSources() {
  const toast = useToast();
  const navigate = useNavigate();
  const { data: people, reload: reloadPeople } = useApi<PersonConfig[]>(() => api.get("/profiles"), []);
  const { data: sources, reload: reloadSources } = useApi<{ demo_mode: boolean; sources: DataSourceRow[] }>(
    () => api.get("/data-sources"), []
  );
  const [jobStatus, setJobStatus] = useState<string>("");
  const [historyFor, setHistoryFor] = useState<{ id: string; name: string } | null>(null);

  const reloadAll = () => { reloadPeople(); reloadSources(); };

  const runAnalysis = async () => {
    setJobStatus("Starting analysis...");
    const { job_id } = await api.post<{ job_id: string }>("/analysis/run", { skip_nlp: false });
    pollAnalysis(job_id, setJobStatus, reloadAll, toast, navigate);
  };

  const forceReanalyze = async () => {
    // Bypasses the NLP cache (data/analysis/nlp_cache.json) so every
    // content/comment row is re-classified from scratch instead of reusing
    // whatever was cached before -- the only way to pick up a model change
    // (e.g. Gemini just enabled, or SENTIMENT_MODEL just set) for rows that
    // were already analyzed. Confirm first: on a large dataset this re-runs
    // NLP on everything, which is slower and, if Gemini is enabled, spends
    // Gemini quota re-classifying Comment Sentiment for rows that already
    // had a result.
    if (!window.confirm(
      "Force re-analyze ALL content and comments, ignoring cached results?\n\n" +
      "This re-runs narrative/sentiment/theme/issue classification for every row " +
      "(local models/lexicon), and if Gemini NLP is enabled, re-classifies Comment " +
      "Sentiment via Gemini too -- which uses API quota. This can take a while on a " +
      "large dataset."
    )) return;
    setJobStatus("Starting forced re-analysis...");
    const { job_id } = await api.post<{ job_id: string }>("/analysis/run", { skip_nlp: false, force_reanalyze: true });
    pollAnalysis(job_id, setJobStatus, reloadAll, toast, navigate);
  };

  return (
    <div className="space-y-6">
      {sources?.demo_mode && (
        <div className="rounded-md border border-gold/60 bg-gold/10 px-4 py-2 text-xs font-semibold text-dark">
          DEMO MODE is active -- data shown across the app is synthetic. Disable it in Settings once you have real scraped data.
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-dark">Person Configuration</h2>
        <div className="flex gap-2">
          <button onClick={reloadAll} className="flex items-center gap-1 rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10">
            <RefreshCw size={13} /> Refresh
          </button>
          <button onClick={runAnalysis} className="flex items-center gap-1 rounded-md bg-navy px-3 py-1.5 text-xs font-semibold text-white hover:bg-navy/90">
            <PlayCircle size={13} /> Run Analysis
          </button>
          <button onClick={forceReanalyze} title="Ignore cached NLP results and re-classify everything -- use after enabling Gemini or a local sentiment model so already-analyzed rows pick it up"
            className="flex items-center gap-1 rounded-md border border-navy/60 px-3 py-1.5 text-xs font-semibold text-navy hover:bg-navy/10">
            <RefreshCw size={13} /> Force Reanalyze
          </button>
        </div>
      </div>
      {jobStatus && <div className="rounded-md bg-navy/5 px-3 py-2 text-xs text-navy">{jobStatus}</div>}

      <AddPersonForm onAdded={reloadAll} />

      <div className="space-y-4">
        {(people ?? []).map((person) => (
          <PersonCard key={person.id} person={person} onChanged={reloadAll} toast={toast} navigate={navigate} onViewHistory={setHistoryFor} />
        ))}
      </div>

      <ScrapeHistoryDrawer personId={historyFor?.id ?? null} personName={historyFor?.name ?? ""} onClose={() => setHistoryFor(null)} />

      <div>
        <h2 className="mb-2 text-sm font-semibold text-dark">Data Source Status</h2>
        <div className="overflow-x-auto rounded-xl border border-silver/60 bg-white shadow-card">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-silver/60 bg-silver/10 text-left text-xs uppercase text-dark/50">
                <th className="px-3 py-2">Person</th><th className="px-3 py-2">Platform</th>
                <th className="px-3 py-2">Last Scraped</th>
                <th className="px-3 py-2">Data Timeline</th>
                <th className="px-3 py-2 text-right">Content</th>
                <th className="px-3 py-2 text-right">Comments</th><th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {(sources?.sources ?? []).map((row, i) => (
                <tr key={i} className="border-t border-silver/30">
                  <td className="px-3 py-2">{row.person_name}</td>
                  <td className="px-3 py-2 capitalize">{row.platform}</td>
                  <td className="px-3 py-2">{fmtDateTime(row.last_scraped)}</td>
                  <td className="px-3 py-2"><DataTimeline row={row} /></td>
                  <td className="px-3 py-2 text-right">{fmtNum(row.content_count)}</td>
                  <td className="px-3 py-2 text-right">{fmtNum(row.comments_count)}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={row.status} />
                    {row.errors.length > 0 && <div className="mt-0.5 text-[10px] text-red-600">{row.errors.slice(0, 1).join("; ")}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/** How many days of real posts were actually collected -- distinct from
 * the --since/--until window that was *requested* of the scraper (shown
 * on hover): a person who posts less often than the window allows will
 * show a narrower span here, which is a fact about them, not a scraper
 * failure. */
function DataTimeline({ row }: { row: DataSourceRow }) {
  if (!row.earliest_post || !row.latest_post) {
    return <span className="text-xs text-dark/30">N/A</span>;
  }
  const requested = row.scrape_window_since && row.scrape_window_until
    ? `Requested window: ${fmtDate(row.scrape_window_since)} – ${fmtDate(row.scrape_window_until)}`
    : undefined;
  return (
    <div title={requested}>
      <div className="text-xs text-dark/80">
        {fmtDate(row.earliest_post)} – {fmtDate(row.latest_post)}
      </div>
      <div className="text-[10px] text-dark/40">
        {row.days_of_content !== null ? `${fmtNum(row.days_of_content)} day${row.days_of_content === 1 ? "" : "s"} of posts` : ""}
      </div>
    </div>
  );
}

interface ScrapeRun {
  run_id: string; platform: string; since: string | null; until: string | null;
  started_at: string | null; finished_at: string | null;
  followers: number | null; followers_raw: string | null;
  posts_scanned: number | null; comments_new: number | null; errors: string[];
}

/** Every scrape run ever recorded for one person, both platforms -- not
 * just the single "last scraped" timestamp the summary table shows.
 * Backed by GET /api/data-sources/{person_id}/history. */
function ScrapeHistoryDrawer({
  personId, personName, onClose,
}: { personId: string | null; personName: string; onClose: () => void }) {
  const { data, loading, error } = useApi<{ runs: ScrapeRun[] }>(
    () => api.get(`/data-sources/${personId}/history`),
    [personId],
    !!personId
  );

  if (!personId) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 flex items-center justify-between border-b border-silver/60 bg-white px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-dark">Scrape History — {personName}</h2>
            <div className="text-xs text-dark/50">Every recorded run, newest first</div>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-silver/20"><X size={18} /></button>
        </div>

        {loading && <div className="p-5 text-sm text-dark/50">Loading...</div>}
        {error && <div className="p-5 text-sm text-red-600">{error}</div>}

        {data && (
          <div className="space-y-3 p-5">
            {data.runs.length === 0 ? (
              <div className="rounded-md border border-dashed border-silver p-6 text-center text-xs text-dark/40">
                No scrape runs recorded yet for this person.
              </div>
            ) : (
              data.runs.map((run) => (
                <div key={run.run_id} className="rounded-xl border border-silver/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold capitalize text-dark">{run.platform}</span>
                    <span className="text-[10px] text-dark/40">{run.run_id}</span>
                  </div>
                  <div className="mt-1 text-xs text-dark/60">
                    Requested window: {fmtDate(run.since)} – {fmtDate(run.until)}
                  </div>
                  <div className="text-xs text-dark/60">
                    Ran: {fmtDateTime(run.started_at)} → {fmtDateTime(run.finished_at)}
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div className="text-[10px] uppercase text-dark/40">Followers</div>
                      <div className="font-semibold text-dark">{run.followers_raw ?? fmtNum(run.followers)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase text-dark/40">Posts Scanned</div>
                      <div className="font-semibold text-dark">{fmtNum(run.posts_scanned)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase text-dark/40">New Comments</div>
                      <div className="font-semibold text-dark">{fmtNum(run.comments_new)}</div>
                    </div>
                  </div>
                  {run.errors?.length > 0 && (
                    <div className="mt-2 rounded-md bg-red-50 p-2 text-[11px] text-red-700">
                      {run.errors.slice(0, 3).join("; ")}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    loaded: "bg-emerald-100 text-emerald-700", partial: "bg-amber-100 text-amber-700",
    not_loaded: "bg-silver/40 text-dark/60", not_configured: "bg-silver/20 text-dark/40",
  };
  const label: Record<string, string> = {
    loaded: "Loaded", partial: "Partial", not_loaded: "Not Loaded", not_configured: "Not Configured",
  };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] ?? ""}`}>{label[status] ?? status}</span>;
}

function AddPersonForm({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [ig, setIg] = useState("");
  const [fb, setFb] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.post("/profiles", { name, instagram_url: ig || null, facebook_url: fb || null });
      setName(""); setIg(""); setFb(""); setOpen(false);
      onAdded();
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="flex items-center gap-1.5 rounded-md border border-dashed border-navy/40 px-3 py-2 text-xs font-semibold text-navy hover:bg-navy/5">
        <Plus size={14} /> Add Person
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <input className="rounded-md border border-silver/70 px-2 py-1.5 text-sm" placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="rounded-md border border-silver/70 px-2 py-1.5 text-sm" placeholder="Instagram URL" value={ig} onChange={(e) => setIg(e.target.value)} />
        <input className="rounded-md border border-silver/70 px-2 py-1.5 text-sm" placeholder="Facebook URL" value={fb} onChange={(e) => setFb(e.target.value)} />
      </div>
      <div className="mt-3 flex gap-2">
        <button disabled={saving} onClick={submit} className="rounded-md bg-navy px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">Save Person</button>
        <button onClick={() => setOpen(false)} className="rounded-md border border-silver px-3 py-1.5 text-xs">Cancel</button>
      </div>
    </div>
  );
}

function PersonCard({
  person, onChanged, toast, navigate, onViewHistory,
}: {
  person: PersonConfig; onChanged: () => void; toast: ReturnType<typeof useToast>;
  navigate: ReturnType<typeof useNavigate>; onViewHistory: (person: { id: string; name: string }) => void;
}) {
  const [importDir, setImportDir] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(person.name);
  const [ig, setIg] = useState(person.instagram_url ?? "");
  const [fb, setFb] = useState(person.facebook_url ?? "");
  const [saving, setSaving] = useState(false);
  // The scrape's --days window -- previously hardcoded to 30 with no way
  // to change it from the UI at all.
  const [days, setDays] = useState(30);

  const saveEdit = async () => {
    setSaving(true);
    try {
      await api.put(`/profiles/${person.id}`, { name, instagram_url: ig || null, facebook_url: fb || null });
      setEditing(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  // Only scrape platforms that actually have a URL configured -- e.g. a
  // person who doesn't use Facebook shouldn't have a Facebook scrape
  // attempted (and fail) just because "Start Scraping" used to hardcode both.
  const configuredPlatforms = [
    person.instagram_url ? "instagram" : null,
    person.facebook_url ? "facebook" : null,
  ].filter((p): p is string => p !== null);

  const startScrape = async (platforms: string[]) => {
    setStatus(`Starting scrape (last ${days} day${days === 1 ? "" : "s"}; a browser window may open)...`);
    try {
      const { job_id } = await api.post<{ job_id: string }>("/scrape/start", {
        person_id: person.id, platforms, days, headed: true,
      });
      pollScrape(job_id, person.name, setStatus, onChanged, toast, () => runAnalysisFromToast(toast, onChanged, navigate));
    } catch (e: any) {
      setStatus(`Failed to start: ${e.message}`);
    }
  };

  const importExisting = async (platform: string) => {
    const source_dir = importDir[platform];
    if (!source_dir) return;
    setStatus(`Importing ${platform} data...`);
    try {
      await api.post("/scrape/import", { person_id: person.id, platform, source_dir });
      setStatus(`Imported ${platform} data from ${source_dir}.`);
      onChanged();
    } catch (e: any) {
      setStatus(`Import failed: ${e.message}`);
    }
  };

  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      {editing ? (
        <div className="space-y-2">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <input className="rounded-md border border-silver/70 px-2 py-1.5 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" />
            <input className="rounded-md border border-silver/70 px-2 py-1.5 text-sm" value={ig} onChange={(e) => setIg(e.target.value)} placeholder="Instagram URL" />
            <input className="rounded-md border border-silver/70 px-2 py-1.5 text-sm" value={fb} onChange={(e) => setFb(e.target.value)} placeholder="Facebook URL" />
          </div>
          <div className="flex gap-2">
            <button disabled={saving} onClick={saveEdit} className="rounded-md bg-navy px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">Save</button>
            <button onClick={() => setEditing(false)} className="flex items-center gap-1 rounded-md border border-silver px-3 py-1.5 text-xs"><X size={12} /> Cancel</button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-dark">{person.name}</div>
            <div className="text-xs text-dark/40">
              {person.instagram_url ?? "No Instagram URL"} · {person.facebook_url ?? "No Facebook URL"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setEditing(true)} className="flex items-center gap-1 rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10">
              <Pencil size={12} /> Edit
            </button>
            <button onClick={() => onViewHistory({ id: person.id, name: person.name })} className="flex items-center gap-1 rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10">
              <History size={12} /> History
            </button>
            <label className="flex items-center gap-1.5 text-xs text-dark/60" title="How many days back to scrape from today">
              Days
              <input
                type="number" min={1} max={365} value={days}
                onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
                className="w-16 rounded-md border border-silver/70 px-2 py-1.5 text-xs"
              />
            </label>
            <button
              disabled={configuredPlatforms.length === 0}
              onClick={() => startScrape(configuredPlatforms)}
              title={configuredPlatforms.length ? `Scrapes: ${configuredPlatforms.join(", ")}` : "Add an Instagram or Facebook URL first"}
              className="flex items-center gap-1 rounded-md bg-navy px-3 py-1.5 text-xs font-semibold text-white hover:bg-navy/90 disabled:opacity-40"
            >
              <PlayCircle size={13} /> Start Scraping{configuredPlatforms.length === 1 ? ` (${configuredPlatforms[0]} only)` : ""}
            </button>
          </div>
        </div>
      )}

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {(["instagram", "facebook"] as const).map((platform) => (
          <div key={platform} className="flex items-center gap-2 rounded-md border border-silver/50 p-2">
            <input
              className="flex-1 min-w-0 rounded border border-silver/60 px-2 py-1 text-xs"
              placeholder={`Existing ${platform} output folder path`}
              value={importDir[platform] ?? ""}
              onChange={(e) => setImportDir((d) => ({ ...d, [platform]: e.target.value }))}
            />
            <button onClick={() => importExisting(platform)} className="flex shrink-0 items-center gap-1 rounded-md border border-silver/80 px-2 py-1 text-xs hover:bg-silver/10">
              <UploadCloud size={12} /> Load Existing
            </button>
          </div>
        ))}
      </div>
      {status && <div className="mt-2 text-xs text-dark/60">{status}</div>}
    </div>
  );
}

/** Polls a scrape job to completion, then pops a toast (spec: "show pop
 * then analysis the result") with a one-click "Run Analysis" action instead
 * of leaving the user to notice a status line changed. */
async function pollScrape(
  jobId: string, personName: string, setStatus: (s: string) => void, onDone: () => void,
  toast: ReturnType<typeof useToast>, runAnalysis: () => void,
) {
  const tick = async () => {
    const job = await api.get<any>(`/scrape/status/${jobId}`);
    if (job.status === "completed" || job.status === "failed") {
      const summary = summarizeResult(job);
      setStatus(summary);
      onDone();
      const anySucceeded = job.result && Object.values(job.result).some((r: any) => r?.ok === true);
      toast.show({
        kind: job.status === "failed" ? "error" : anySucceeded ? "success" : "error",
        title: `Scraping finished -- ${personName}`,
        message: summary,
        action: anySucceeded ? { label: "Run Analysis", onClick: runAnalysis } : undefined,
      });
      return;
    }
    setStatus(`${job.status}: ${job.status_message ?? ""}`);
    setTimeout(tick, 1500);
  };
  tick();
}

function summarizeResult(job: any): string {
  if (job.status === "failed") return `Failed: ${job.error ?? "unknown error"}`;
  const result = job.result;
  if (!result || typeof result !== "object") return "Completed.";
  const parts: string[] = [];
  for (const [platform, r] of Object.entries<any>(result)) {
    if (r?.ok === true) parts.push(`${platform}: succeeded`);
    else if (r?.ok === false) parts.push(`${platform} FAILED: ${r.error ?? "unknown error"}`);
  }
  return parts.length ? parts.join(" · ") : "Completed.";
}

async function runAnalysisFromToast(
  toast: ReturnType<typeof useToast>, onChanged: () => void, navigate: ReturnType<typeof useNavigate>,
) {
  toast.show({ kind: "info", title: "Running analysis...", message: "Normalizing data and classifying content." });
  const { job_id } = await api.post<{ job_id: string }>("/analysis/run", { skip_nlp: false });
  pollAnalysis(job_id, () => {}, onChanged, toast, navigate);
}

async function pollAnalysis(
  jobId: string, setStatus: (s: string) => void, onDone: () => void,
  toast: ReturnType<typeof useToast>, navigate: ReturnType<typeof useNavigate>,
) {
  const tick = async () => {
    const job = await api.get<any>(`/scrape/status/${jobId}`);
    setStatus(`${job.status}: ${job.status_message ?? ""}`);
    if (job.status === "completed" || job.status === "failed") {
      onDone();
      if (job.status === "completed") {
        const ingestion = job.result?.ingestion;
        toast.show({
          kind: "success",
          title: "Analysis complete",
          message: ingestion ? `${ingestion.content_rows} content rows, ${ingestion.comments_rows} comments processed.` : undefined,
          action: { label: "View Comparison", onClick: () => navigate("/comparison") },
        });
      } else {
        toast.show({ kind: "error", title: "Analysis failed", message: job.error ?? undefined });
      }
      return;
    }
    setTimeout(tick, 1500);
  };
  tick();
}
