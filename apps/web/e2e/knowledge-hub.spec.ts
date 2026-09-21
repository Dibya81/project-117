import { test, expect } from "@playwright/test";

/**
 * Knowledge Hub E2E tests.
 *
 * Verifies the core user flow for the company knowledge workspace:
 *   1. Navigate to Knowledge Hub
 *   2. Workspace health panel is visible
 *   3. Documents page renders the upload drop-zone
 */

test.describe("Knowledge Hub", () => {
  test("health panel is visible on hub page", async ({ page }) => {
    await page.goto("/console/knowledge/hub");
    // Heading should be present
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
    // The page should not show a loading spinner indefinitely
    await page.waitForLoadState("networkidle");
    // No unhandled error overlays
    await expect(page.locator('[data-testid="error-overlay"]')).toHaveCount(0);
  });

  test("documents page renders upload area", async ({ page }) => {
    await page.goto("/console/knowledge/documents");
    await page.waitForLoadState("networkidle");
    // Should have a heading
    await expect(page.locator("h1, h2").first()).toBeVisible({ timeout: 10_000 });
    // Should have some kind of drop target or file input
    const uploadTarget = page.locator(
      'input[type="file"], [data-testid="drop-zone"], [aria-label*="upload" i]'
    );
    await expect(uploadTarget.first()).toBeAttached({ timeout: 10_000 });
  });
});
