import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // MapLibre's distributed entry is UMD. Make its interop explicit so Vite's
  // first dependency scan and later requests agree on the module's exports.
  optimizeDeps: {
    include: ["maplibre-gl"],
    needsInterop: ["maplibre-gl"],
  },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
  build: {
    // MapLibre's self-contained renderer/worker is ~1 MB before gzip.
    chunkSizeWarningLimit: 1100,
    rollupOptions: { output: { manualChunks: { maplibre: ["maplibre-gl"] } } },
  },
});
