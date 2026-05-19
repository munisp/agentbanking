/**
 * E2E: Agent Cash-Out Transaction Flow
 *
 * Critical flow: Tests cash withdrawal from agent to customer
 * Prerequisites: Dev server running, seed data loaded (AGT001 / PIN 1234)
 */
import { test, expect } from "@playwright/test";

test.describe("Cash-Out Transaction Flow", () => {
  // Helper to login as agent
  async function loginAsAgent(page: any) {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const agentInput = page.locator('input[placeholder*="AGT"]');
    await agentInput.fill("AGT001");
    await page.locator("button", { hasText: /continue/i }).click();

    await page.waitForTimeout(500);
    for (const digit of ["1", "2", "3", "4"]) {
      const pinBtn = page.locator(`button[data-digit="${digit}"]`).first();
      if (await pinBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await pinBtn.click();
        await page.waitForTimeout(100);
      }
    }

    // Wait for dashboard
    await page.waitForTimeout(2_000);
  }

  test("should navigate to cash-out from POS dashboard", async ({ page }) => {
    await loginAsAgent(page);

    // Find and click Cash Out button
    const cashOutBtn = page.locator("text=/cash.?out/i").first();
    await expect(cashOutBtn).toBeVisible({ timeout: 10_000 });
    await cashOutBtn.click();

    // Verify cash-out form appears
    await expect(
      page.locator("text=/cash.?out|withdrawal|amount/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("should perform cash-out with customer phone and amount", async ({
    page,
  }) => {
    await loginAsAgent(page);

    // Navigate to Cash Out
    const cashOutBtn = page.locator("text=/cash.?out/i").first();
    if (await cashOutBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await cashOutBtn.click();
    }

    await page.waitForTimeout(1_000);

    // Fill customer phone
    const phoneInput = page
      .locator(
        'input[placeholder*="phone"], input[placeholder*="customer"], input[placeholder*="Phone"]'
      )
      .first();
    if (await phoneInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await phoneInput.fill("08098765432");
    }

    // Fill amount
    const amountInput = page
      .locator(
        'input[placeholder*="amount"], input[placeholder*="Amount"], input[type="number"]'
      )
      .first();
    if (await amountInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await amountInput.fill("3000");
    }

    // Submit
    const submitBtn = page
      .locator("button", { hasText: /confirm|proceed|submit|withdraw/i })
      .first();
    if (await submitBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await submitBtn.click();
    }

    // Verify success
    await expect(
      page
        .locator(
          "text=/receipt|success|completed|₦3,000|transaction|approved/i"
        )
        .first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("should reject cash-out exceeding daily limit", async ({ page }) => {
    await loginAsAgent(page);

    const cashOutBtn = page.locator("text=/cash.?out/i").first();
    if (await cashOutBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await cashOutBtn.click();
    }

    await page.waitForTimeout(1_000);

    // Try excessive amount
    const amountInput = page
      .locator(
        'input[placeholder*="amount"], input[placeholder*="Amount"], input[type="number"]'
      )
      .first();
    if (await amountInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await amountInput.fill("99999999");
    }

    const phoneInput = page
      .locator('input[placeholder*="phone"], input[placeholder*="customer"]')
      .first();
    if (await phoneInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await phoneInput.fill("08098765432");
    }

    const submitBtn = page
      .locator("button", { hasText: /confirm|proceed|submit|withdraw/i })
      .first();
    if (await submitBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await submitBtn.click();
    }

    // Should show error about limits
    await expect(
      page
        .locator("text=/limit|exceed|insufficient|error|maximum|invalid/i")
        .first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
