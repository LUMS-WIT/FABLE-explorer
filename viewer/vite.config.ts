import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages serves a project site under /<repo>/. Override with
// VITE_BASE for a custom domain ("/") or a different repo name.
const base = process.env.VITE_BASE ?? "/FABLE_Pakistan/";

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
});
