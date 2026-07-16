import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "sonner": path.resolve(__dirname, "./src/lib/sonner-stub.ts"),
      "wouter": path.resolve(__dirname, "./src/lib/wouter-stub.ts"),
    },
  },
  server: {
    port: 5174,
  },
});
