import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [status, setStatus] = useState("");

  const load = () => api.get<any>("/settings").then(setSettings);
  useEffect(() => { load(); }, []);

  const update = async (patch: Record<string, unknown>) => {
    const updated = await api.put<any>("/settings", patch);
    setSettings(updated);
  };

  const loadDemo = async () => {
    setStatus("Generating demo dataset...");
    const result = await api.post<any>("/settings/demo-data");
    setStatus(`Demo dataset loaded: ${result.content_rows} content rows, ${result.comment_rows} comments.`);
    load();
  };

  const disableDemo = async () => {
    await api.post("/settings/demo-data/disable");
    setStatus("Demo mode disabled -- real scraped data will be shown.");
    load();
  };

  if (!settings) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <Section title="Mode">
        <div className={`rounded-md px-3 py-2 text-sm font-semibold ${settings.demo_mode ? "bg-gold/20 text-dark" : "bg-navy/10 text-navy"}`}>
          {settings.demo_mode ? "DEMO MODE" : settings.nlp_enabled && settings.gemini_api_key_configured ? "GEMINI NLP ENABLED" : "LOCAL ANALYSIS MODE"}
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={loadDemo} className="rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10">Load Demo Data</button>
          {settings.demo_mode && (
            <button onClick={disableDemo} className="rounded-md border border-silver/80 px-3 py-1.5 text-xs font-medium hover:bg-silver/10">Disable Demo Mode</button>
          )}
        </div>
        {status && <p className="mt-2 text-xs text-dark/60">{status}</p>}
      </Section>

      <Section title="NLP / Gemini">
        <Row label="Gemini API key">
          <span className="text-sm">
            {settings.gemini_api_key_configured ? "Configured (via GEMINI_API_KEY env var)" : "Not configured"}
          </span>
        </Row>
        <p className="text-[11px] text-dark/40">Set GEMINI_API_KEY in the project's .env file -- never entered here, never logged.</p>
        <Row label="Model">
          <input className="w-56 rounded-md border border-silver/70 px-2 py-1 text-sm" value={settings.gemini_model}
            onChange={(e) => setSettings({ ...settings, gemini_model: e.target.value })}
            onBlur={(e) => update({ gemini_model: e.target.value })} />
        </Row>
        <Row label="Enable Gemini NLP">
          <Toggle checked={!!settings.nlp_enabled} onChange={(v) => update({ nlp_enabled: v })} />
        </Row>
        <Row label="Analysis batch size">
          <input type="number" className="w-24 rounded-md border border-silver/70 px-2 py-1 text-sm" value={settings.analysis_batch_size}
            onChange={(e) => setSettings({ ...settings, analysis_batch_size: Number(e.target.value) })}
            onBlur={(e) => update({ analysis_batch_size: Number(e.target.value) })} />
        </Row>
      </Section>

      <Section title="Display">
        <Row label="Data directory"><span className="text-sm text-dark/60">{settings.data_directory}</span></Row>
        <Row label="Date format"><span className="text-sm">{settings.date_format}</span></Row>
        <Row label="Theme">
          <select className="rounded-md border border-silver/70 px-2 py-1 text-sm" value={settings.theme}
            onChange={(e) => update({ theme: e.target.value })}>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </Row>
        <Row label="Default comparison period (days)">
          <input type="number" className="w-24 rounded-md border border-silver/70 px-2 py-1 text-sm" value={settings.default_comparison_period_days}
            onChange={(e) => setSettings({ ...settings, default_comparison_period_days: Number(e.target.value) })}
            onBlur={(e) => update({ default_comparison_period_days: Number(e.target.value) })} />
        </Row>
        <Row label="Auto-refresh">
          <Toggle checked={!!settings.auto_refresh} onChange={(v) => update({ auto_refresh: v })} />
        </Row>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-silver/60 bg-white p-4 shadow-card transition-shadow duration-150 ease-smooth hover:shadow-card-hover">
      <h3 className="mb-3 text-sm font-semibold text-dark">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-dark/70">{label}</span>
      {children}
    </div>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`h-5 w-9 rounded-full transition-colors ${checked ? "bg-navy" : "bg-silver"}`}
    >
      <span className={`block h-4 w-4 translate-y-0.5 rounded-full bg-white transition-transform ${checked ? "translate-x-4" : "translate-x-0.5"}`} />
    </button>
  );
}
