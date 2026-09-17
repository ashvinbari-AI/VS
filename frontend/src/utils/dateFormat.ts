/** The user's chosen date pattern (Settings page's "Date format" field),
 * kept as a small module-level singleton rather than React context --
 * fmtDate/fmtDateTime in utils/format.ts are plain functions called from
 * dozens of places, not hooks, so they read this directly. Initialized
 * once from GET /api/settings on app load (AppLayout) and updated
 * immediately whenever the Settings page saves a new value, so every
 * already-rendered date re-renders on next paint without a full reload. */

export const DATE_FORMAT_PRESETS = ["DD MMM YYYY", "MMM DD, YYYY", "DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"];
const DEFAULT_PATTERN = "DD MMM YYYY";

let currentPattern: string = DEFAULT_PATTERN;
const listeners = new Set<() => void>();

export function setDateFormat(pattern: string | null | undefined): void {
  currentPattern = pattern && DATE_FORMAT_PRESETS.includes(pattern) ? pattern : DEFAULT_PATTERN;
  listeners.forEach((fn) => fn());
}

export function getDateFormat(): string {
  return currentPattern;
}

/** Optional: call to be notified when the format changes (e.g. to force a
 * re-render of something memoized). Not required for plain formatter
 * calls, which just read getDateFormat() fresh each time they run. */
export function onDateFormatChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}

/** Renders a Date against a pattern using DD/MM/MMM/MMMM/YYYY/YY tokens
 * (the same vocabulary the Settings page's preset list uses). Longer
 * tokens are replaced before their shorter substrings (YYYY before YY,
 * MMMM before MMM before MM) so there's no partial-match ambiguity. */
export function applyDatePattern(d: Date, pattern: string): string {
  const day = d.getDate();
  const month = d.getMonth();
  const year = d.getFullYear();
  return pattern
    .replace(/YYYY/g, String(year))
    .replace(/YY/g, String(year).slice(-2))
    .replace(/MMMM/g, MONTHS_LONG[month])
    .replace(/MMM/g, MONTHS_SHORT[month])
    .replace(/MM/g, pad2(month + 1))
    .replace(/DD/g, pad2(day));
}
