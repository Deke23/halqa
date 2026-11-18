import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/",
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    port: Number(process.env.WEB_PORT ?? 5173),
    strictPort: true,
    proxy: {
      "/api": { target: process.env.API_TARGET ?? "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
