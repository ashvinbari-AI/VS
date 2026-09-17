/** @type {import('tailwindcss').Config} */
export default {
  // Class-based (not 'media'/prefers-color-scheme): driven by the user's
  // own Settings > Theme choice (see src/utils/themeStore.ts), which
  // toggles a `dark` class on <html> -- not the OS setting.
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Deep navy + warm gold/orange dashboard theme.
        // Keep in sync with src/utils/theme.ts's COLOR_PRIMARY/COLOR_SECONDARY
        // (Recharts needs raw hex, not Tailwind classes).
        navy: {
          DEFAULT: "#16305A",
          50: "#EEF2F8",
          100: "#D6E0EE",
          200: "#AFC2DC",
          300: "#7E9BC1",
          400: "#4C71A0",
          500: "#2A4F80",
          600: "#1C3B65",
          700: "#16305A", // DEFAULT
          800: "#102544",
          900: "#0B1A31",
          950: "#070F1D",
        },
        gold: {
          DEFAULT: "#F5A623",
          50: "#FFF7E8",
          100: "#FEECC6",
          200: "#FDD98D",
          300: "#FBC155",
          400: "#F8AF33",
          500: "#F5A623", // DEFAULT
          600: "#DD8A0F",
          700: "#B76B0B",
          800: "#8F520E",
          900: "#6E400F",
        },
        dark: "#1B2431",
        silver: "#DDE1E8",
        offwhite: "#F4F6FA",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "Segoe UI", "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 37, 68, 0.04), 0 1px 6px rgba(16, 37, 68, 0.06)",
        "card-hover": "0 4px 10px rgba(16, 37, 68, 0.08), 0 2px 20px rgba(16, 37, 68, 0.08)",
        nav: "2px 0 16px rgba(7, 15, 29, 0.15)",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
    },
  },
  plugins: [],
};
