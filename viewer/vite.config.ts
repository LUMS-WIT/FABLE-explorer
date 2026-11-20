import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base: the built site works under any path (GitHub Pages project
// site, a custom domain, `python -m fable.compute view`). The deploy workflow
// may still pass an absolute VITE_BASE.
const base = process.env.VITE_BASE ?? "./";

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
});
