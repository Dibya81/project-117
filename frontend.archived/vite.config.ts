import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Two things worth knowing about this config:
 *
 * 1. `publicDir` points at the existing `project-117-simulation/public`
 *    package rather than copying its data into this project. The plant JSON has
 *    exactly one home, so regenerating it with `database/generate_seed.py` is
 *    picked up here with no copy step. Vite serves it at `/data/*.json` in dev
 *    and copies it into `dist/` on build.
 *
 * 2. No proxy is configured on purpose. The orchestrator is reached over a raw
 *    WebSocket at VITE_ORCHESTRATOR_WS_URL, not through the dev server, so the
 *    URL you configure is the URL that is used.
 */
export default defineConfig({
  plugins: [react()],
  publicDir: "../project-117-simulation/public",
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: true, emptyOutDir: true },
});
