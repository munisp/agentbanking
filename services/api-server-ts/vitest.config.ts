import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    // Global setup file for mocking external services
    setupFiles: ["./vitest.setup.ts"],
    // Exclude Playwright E2E tests from Vitest runner
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/*.e2e.ts",
      "**/*.e2e.spec.ts",
      "**/playwright/**",
      "**/e2e/**",
    ],
    // Environment
    environment: "node",
    // Test timeout (30s for integration-style tests)
    testTimeout: 30000,
    hookTimeout: 30000,
    // Globals (describe, it, expect available without import)
    globals: false,
    // Reporter
    reporter: "verbose",
    // Coverage
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      exclude: [
        "node_modules/**",
        "dist/**",
        "drizzle/**",
        "**/*.d.ts",
        "vitest.config.ts",
        "vitest.setup.ts",
      ],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./server"),
      "@shared": path.resolve(__dirname, "./shared"),
      "@drizzle": path.resolve(__dirname, "./drizzle"),
    },
  },
});
