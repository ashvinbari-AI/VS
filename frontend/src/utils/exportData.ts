/** Local-only export helpers (spec section 43) -- builds a Blob in the
 * browser and triggers a normal file download. No network call, no cloud
 * service involved. */

export function exportJson(filename: string, data: unknown): void {
  download(filename, JSON.stringify(data, null, 2), "application/json");
}

export function exportCsv<T extends object>(filename: string, rows: T[]): void {
  if (rows.length === 0) {
    download(filename, "", "text/csv");
    return;
  }
  const records = rows as unknown as Record<string, unknown>[];
  const headers = Array.from(records.reduce((set, row) => {
    Object.keys(row).forEach((k) => set.add(k));
    return set;
  }, new Set<string>()));
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(","), ...records.map((r) => headers.map((h) => escape(r[h])).join(","))];
  download(filename, lines.join("\n"), "text/csv");
}

function download(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
