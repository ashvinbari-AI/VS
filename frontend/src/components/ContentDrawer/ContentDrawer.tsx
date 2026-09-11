import { ExternalLink, X } from "lucide-react";
import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { api } from "../../services/api";
import { fmtDateTime, fmtNum, fmtPct } from "../../utils/format";
import type { CommentItem } from "../../types/api";

interface ContentDetail {
  content: any;
  comments: CommentItem[];
}

/** The click-through detail drawer (spec sections 18/19/42/43): full record,
 * comments, and a "View Raw Data" toggle showing the literal scraped JSONL
 * line this row was built from -- the audit/evidence trail. */
export function ContentDrawer({ contentId, onClose }: { contentId: string | null; onClose: () => void }) {
  const { data, loading, error } = useApi<ContentDetail>(
    () => api.get(`/content/${contentId}`),
    [contentId],
    !!contentId
  );
  const [showRaw, setShowRaw] = useState(false);
  const { data: raw } = useApi<any>(() => api.get(`/content/${contentId}/raw`), [contentId], showRaw && !!contentId);

  if (!contentId) return null;
  const c = data?.content;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 flex items-center justify-between border-b border-silver/60 bg-white px-5 py-3">
          <h2 className="text-sm font-semibold text-dark">Content Detail</h2>
          <button onClick={onClose} className="rounded p-1 hover:bg-silver/20"><X size={18} /></button>
        </div>

        {loading && <div className="p-5 text-sm text-dark/50">Loading...</div>}
        {error && <div className="p-5 text-sm text-red-600">{error}</div>}

        {c && (
          <div className="space-y-5 p-5">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Field label="Person" value={c.person_name} />
              <Field label="Platform" value={c.platform} />
              <Field label="Content Type" value={c.content_type} />
              <Field label="Published" value={fmtDateTime(c.published_at_local || c.published_at)} />
              <Field label="Likes" value={fmtNum(c.likes)} />
              <Field label="Comments" value={fmtNum(c.comments_count)} />
              <Field label="Shares" value={c.shares === null ? "N/A" : fmtNum(c.shares)} />
              <Field label="Engagement" value={fmtNum(c.engagement)} />
              <Field label="Engagement Rate" value={c.engagement_rate_pct != null ? fmtPct(c.engagement_rate_pct) : "N/A"} />
              <Field label="Followers at Collection" value={fmtNum(c.followers_at_collection)} />
            </div>

            {c.content_url && (
              <a href={c.content_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-navy hover:underline">
                <ExternalLink size={12} /> Open Original Post
              </a>
            )}

            <div>
              <div className="text-xs font-semibold uppercase text-dark/50">Caption</div>
              <p className="mt-1 whitespace-pre-wrap text-sm text-dark">{c.caption || "N/A"}</p>
            </div>

            {c.hashtags?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {c.hashtags.map((h: string) => (
                  <span key={h} className="rounded-full bg-navy/10 px-2 py-0.5 text-xs text-navy">#{h}</span>
                ))}
              </div>
            )}

            <div className="rounded-md border border-silver/60 bg-silver/5 p-3">
              <div className="mb-1 text-xs font-semibold uppercase text-dark/50">Model-Classified (AI)</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <Field label="Narrative" value={c.narrative ?? "Not analyzed"} />
                <Field label="Sentiment" value={c.sentiment ?? "Not analyzed"} />
              </div>
              {c.narrative && (
                <div className="mt-1 text-[11px] text-dark/40">
                  Confidence: {c.narrative_confidence ?? "N/A"} · Model: {c.nlp_model ?? "N/A"}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase text-dark/50">Comments ({data.comments.length})</h3>
              </div>
              <div className="max-h-64 space-y-2 overflow-y-auto">
                {data.comments.slice(0, 50).map((cm) => (
                  <div key={cm.comment_id} className="rounded-md border border-silver/40 p-2 text-xs">
                    <div className="flex justify-between text-dark/50">
                      <span>{cm.author_username ?? "N/A"}</span>
                      <span>{fmtDateTime(cm.commented_at)}</span>
                    </div>
                    <div className="mt-1 text-dark">{cm.comment_text ?? "N/A"}</div>
                    <div className="mt-1 flex gap-2 text-[10px] text-dark/40">
                      {cm.sentiment && <span>Sentiment: {cm.sentiment}</span>}
                      {cm.theme && <span>Theme: {cm.theme}</span>}
                      {cm.issues?.length > 0 && <span>Issues: {cm.issues.join(", ")}</span>}
                    </div>
                  </div>
                ))}
                {data.comments.length === 0 && <p className="text-xs text-dark/40">No comments captured.</p>}
              </div>
            </div>

            <button
              onClick={() => setShowRaw((v) => !v)}
              className="w-full rounded-md border border-silver/80 py-2 text-xs font-semibold text-dark hover:bg-silver/10"
            >
              {showRaw ? "Hide Raw Data" : "View Raw Data"}
            </button>
            {showRaw && (
              <div>
                <div className="text-[11px] text-dark/40">Source: {raw?.raw_source_file}</div>
                <pre className="mt-1 max-h-64 overflow-auto rounded-md bg-dark/95 p-3 text-[11px] text-silver">
                  {raw ? JSON.stringify(raw.raw_record, null, 2) : "Loading..."}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="text-[11px] text-dark/40">{label}</div>
      <div className="font-medium capitalize text-dark">{value ?? "N/A"}</div>
    </div>
  );
}
