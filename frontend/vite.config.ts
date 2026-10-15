import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Use MapLibre 6's native named ESM exports without a CommonJS wrapper.
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  worker: { format: "es" },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
  build: {
    // MapLibre's self-contained renderer/worker is ~1 MB before gzip.
    chunkSizeWarningLimit: 1100,
  },
});
