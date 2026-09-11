/** Single source of truth for the chart colors that Recharts needs as raw
 * hex strings (Tailwind's `navy`/`gold` classes only affect DOM elements,
 * not SVG props passed to Recharts). Matches the `navy`/`gold` tokens in
 * tailwind.config.js -- keep both in sync if the palette changes again. */
export const COLOR_PRIMARY = "#16305A"; // Person A / primary accent (navy)
export const COLOR_SECONDARY = "#F5A623"; // Person B / secondary accent (gold/orange)

// Extra chart tones used for grid lines / muted series so pages don't
// hardcode hex strings that drift from the theme.
export const COLOR_GRID = "#E4E8F0";
export const COLOR_MUTED = "#8B93A7";
