import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI backend so the frontend can call it same-origin in dev.
// VITE_STATIC=1 builds the GitHub Pages demo, served from
// https://<username>.github.io/conflictwatch-demo/ (override with VITE_BASE).
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), "VITE_"), ...process.env };
  const isStatic = env.VITE_STATIC === "1";
  return {
    base: isStatic ? env.VITE_BASE ?? "/conflictwatch-demo/" : "/",
    plugins: [react()],
    // the exported snapshot only ships with the static build
    publicDir: isStatic ? "public" : false,
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
