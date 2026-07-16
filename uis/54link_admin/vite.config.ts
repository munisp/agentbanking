import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  server: {
    host: true,
    allowedHosts: ["admin.54link-dev.upi.dev"],
    proxy: Object.fromEntries(
      [
        // Auth & identity
        "/auth", "/admin", "/orchestrator",
        // Core banking
        "/account", "/user", "/ledger", "/document", "/notification",
        // Tenant & features
        "/tenant-management", "/feature-flags-go",
        // Payments & FX
        "/payment-processing-service", "/payment-rails-connectors",
        "/exchange-rate-service", "/mojaloop-connector", "/bill-payment-service",
        // Compliance & risk
        "/fraud", "/fraudfusion", "/txn-monitoring-rules-rs",
        "/kyc", "/kyb-service", "/aml-compliance-dashboard-py",
        "/aml-case-manager-go", "/aml-risk-scoring-rs",
        // Lending
        "/loan", "/loans", "/lpo", "/savings", "/microfinance-engine-go",
        "/group-lending", "/esusu",
        // Agent banking
        "/agent-banking-go",
        // Monitoring & analytics
        "/kpi-engine-go", "/api-metering", "/reporting-service",
        "/monitoring-service",
        // Developer platform
        "/developer-platform",
        // Alerts
        "/alert-rules-go", "/alert-settings-go",
        // Disputes
        "/dispute",
      ].map((prefix) => [
        prefix,
        { target: "https://54link-dev.upi.dev", changeOrigin: true },
      ])
    ),
  },
});
