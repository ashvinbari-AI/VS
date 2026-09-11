import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Local-only dev server: proxies /api to the FastAPI backend so the React
// app never needs CORS workarounds or a hardcoded backend host.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
