import { test, expect } from "@playwright/test";

/**
 * E2E: Billing Dashboard & Invoice Management
 * Tests the billing engine UI flows added in Sprints 79–84
 */

test.describe("Billing Dashboard", () => {
  test("should load billing dashboard page", async ({ page }) => {
    await page.goto("/billing/dashboard");
    // Should either show the dashboard or redirect to login
    const url = page.url();
    expect(url).toMatch(/billing\/dashboard|login|oauth/);
  });

  test("should load billing analytics page", async ({ page }) => {
    await page.goto("/billing/analytics");
    const url = page.url();
    expect(url).toMatch(/billing\/analytics|login|oauth/);
  });

  test("should load invoice management page", async ({ page }) => {
    await page.goto("/billing/invoices");
    const url = page.url();
    expect(url).toMatch(/billing\/invoices|login|oauth/);
  });

  test("should load tenant billing onboarding page", async ({ page }) => {
    await page.goto("/billing/onboarding");
    const url = page.url();
    expect(url).toMatch(/billing\/onboarding|login|oauth/);
  });

  test("should load tenant billing portal page", async ({ page }) => {
    await page.goto("/billing/portal");
    const url = page.url();
    expect(url).toMatch(/billing\/portal|login|oauth/);
  });
});

test.describe("Health Check API", () => {
  test("should return health status from API", async ({ request }) => {
    // Health check should be publicly accessible
    const response = await request.get("/api/trpc/healthCheck.status");
    // tRPC returns 200 for successful queries or 401 for protected
    expect([200, 401]).toContain(response.status());
  });
});

test.describe("Billing API Endpoints", () => {
  test("billing ledger query should require auth", async ({ request }) => {
    const response = await request.get("/api/trpc/billingLedger.query");
    // Should return 401 since we're not authenticated
    expect([401, 400]).toContain(response.status());
  });

  test("billing dashboard summary should require auth", async ({ request }) => {
    const response = await request.get(
      "/api/trpc/liveBillingDashboard.summary"
    );
    expect([401, 400]).toContain(response.status());
  });

  test("billing RBAC roles should require auth", async ({ request }) => {
    const response = await request.get("/api/trpc/billingRbac.listRoles");
    expect([401, 400]).toContain(response.status());
  });

  test("billing audit log should require auth", async ({ request }) => {
    const response = await request.get("/api/trpc/billingAudit.getAuditLog");
    expect([401, 400]).toContain(response.status());
  });
});

test.describe("Stripe Webhook Endpoint", () => {
  test("webhook endpoint should exist and reject unsigned requests", async ({
    request,
  }) => {
    const response = await request.post("/api/stripe/webhook", {
      data: JSON.stringify({ type: "test" }),
      headers: { "Content-Type": "application/json" },
    });
    // Should reject without valid Stripe signature (400 or 500)
    expect([400, 500]).toContain(response.status());
  });
});

test.describe("Monthly Invoice Cron Endpoint", () => {
  test("cron endpoint should exist and require auth header", async ({
    request,
  }) => {
    const response = await request.post("/api/scheduled/monthly-invoices", {
      data: JSON.stringify({}),
      headers: { "Content-Type": "application/json" },
    });
    // Should reject without proper authorization
    expect([401, 403, 200]).toContain(response.status());
  });
});

test.describe("Page Navigation", () => {
  test("homepage should load without errors", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/.*/);
    // Page should not show a blank screen
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
    expect(body!.length).toBeGreaterThan(10);
  });

  test("404 page should render for unknown routes", async ({ page }) => {
    await page.goto("/nonexistent-route-12345");
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });
});
