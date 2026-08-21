import { defineConfig, devices } from "@playwright/test";

/**
 * 54Link POS Shell — Playwright E2E Configuration
 * Run: pnpm exec playwright test
 * Report: pnpm exec playwright show-report
 *
 * round3-W2: testDir fixed — specs live in tests/e2e (the pre-restructure
 * ./e2e directory no longer exists).
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // In CI the server is already started by the workflow step — just reuse it
  webServer: process.env.CI
    ? {
        command: "pnpm dev",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 60_000,
      }
    : undefined,
});
