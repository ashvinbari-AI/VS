/** Single source of truth for the chart colors that Recharts needs as raw
 * hex strings (Tailwind's `navy`/`gold` classes only affect DOM elements,
 * not SVG props passed to Recharts). Matches the `navy`/`gold` tokens in
 * tailwind.config.js -- keep both in sync if the palette changes again. */
export const COLOR_PRIMARY = "#16305A"; // Person A / primary accent (navy)
export const COLOR_SECONDARY = "#F5A623"; // Person B / secondary accent (gold/orange)

/** One color per comparison slot (Person 1, 2, 3, ...). The first two are
 * the original navy/gold so a 2-person comparison looks exactly as before. */
export const PERSON_COLORS = [
  COLOR_PRIMARY, // navy
  COLOR_SECONDARY, // gold
  "#0E9F8E", // teal
  "#D1495B", // crimson
  "#7B5CD6", // violet
  "#3A86C8", // sky blue
];

export function personColor(slot: number): string {
  return PERSON_COLORS[slot % PERSON_COLORS.length];
}

// Extra chart tones used for grid lines / muted series so pages don't
// hardcode hex strings that drift from the theme.
export const COLOR_GRID = "#E4E8F0";
export const COLOR_MUTED = "#8B93A7";
