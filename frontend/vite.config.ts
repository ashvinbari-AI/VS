import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Local-only dev server: proxies /api to the FastAPI backend so the React
// app never needs CORS workarounds or a hardcoded backend host.
// The backend runs on fixed port 3001 (start_all.py). start_all.py also
// passes BACKEND_PORT, so a custom --backend-port is followed too.
const backendPort = process.env.BACKEND_PORT || "3001";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
});
