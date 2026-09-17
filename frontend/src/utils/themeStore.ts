/** Applies the Settings page's "Theme" choice by toggling Tailwind's
 * class-based dark mode (`dark` class on <html> -- see tailwind.config.js's
 * `darkMode: "class"`). A plain function, not React state, so it can be
 * called once at app load (AppLayout) and again immediately whenever
 * Settings saves a new value -- same pattern as utils/dateFormat.ts. */

export function applyTheme(theme: string | null | undefined): void {
  const isDark = theme === "dark";
  document.documentElement.classList.toggle("dark", isDark);
}
