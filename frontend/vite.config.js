import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    assetsDir: "static",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/parser": "http://127.0.0.1:8000",
      "/providers": "http://127.0.0.1:8000",
      "/analysis": "http://127.0.0.1:8000",
      "/scrape": "http://127.0.0.1:8000",
      "/report": "http://127.0.0.1:8000",
      "/checklist": "http://127.0.0.1:8000",
      "/pipeline": "http://127.0.0.1:8000",
      "/prompt": "http://127.0.0.1:8000",
    },
  },
});
