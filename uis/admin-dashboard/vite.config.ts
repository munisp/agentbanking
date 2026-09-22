import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3001,
  },
  build: {
    target: "es2020",
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return;
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return "vendor-react";
          if (/node_modules\/(react-router|react-router-dom|@remix-run|wouter)\//.test(id)) return "vendor-router";
          if (/node_modules\/(recharts|d3-)/.test(id)) return "vendor-charts";
          if (/node_modules\/(leaflet|react-leaflet|@react-leaflet)/.test(id)) return "vendor-maps";
          if (/node_modules\/(framer-motion)/.test(id)) return "vendor-motion";
        },
      },
    },
  },
});
