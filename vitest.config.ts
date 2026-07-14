import { defineConfig } from "vitest/config";
import path from "path";

const templateRoot = path.resolve(import.meta.dirname);

export default defineConfig({
  root: templateRoot,
  resolve: {
    alias: {
      "@": path.resolve(templateRoot, "client", "src"),
      "@shared": path.resolve(templateRoot, "shared"),
      "@assets": path.resolve(templateRoot, "attached_assets"),
    },
  },
  test: {
    setupFiles: ["./vitest.setup.ts"],
    environment: "node",
    env: {
      // Provide a well-formed test URL so Keycloak URL-construction tests
      // (buildAuthorizationUrl) can run without a live Keycloak instance.
      // This does NOT enable real Keycloak auth — it only satisfies new URL().
      KEYCLOAK_URL: "https://auth.test.54link.io",
      KEYCLOAK_REALM: "54link",
      KEYCLOAK_CLIENT_ID: "pos-shell",
    },
    testTimeout: 30000,
    include: [
      "server/**/*.test.ts",
      "server/**/*.spec.ts",
      "tests/**/*.test.ts",
      "tests/**/*.spec.ts",
    ],
    // Playwright E2E specs use Playwright's own test() API and must be run
    // with `playwright test` — NOT vitest. Including them in vitest causes
    // a "test() called outside of a test suite" error.
    exclude: [
      "tests/e2e/**/*.spec.ts",
      "tests/e2e/**/*.test.ts",
      "**/node_modules/**",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["server/**/*.ts"],
      exclude: ["server/_core/**", "server/**/*.test.ts", "server/**/*.d.ts"],
    },
  },
});
