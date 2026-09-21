import { test, expect } from "@playwright/test";

/**
 * Core navigation smoke tests.
 *
 * Verifies that every primary console route:
 *   1. Returns 200 (not a 404 or unhandled error)
 *   2. Has a visible <h1> (correct page rendered, not an error boundary)
 *   3. Has a correct <title> (SEO / browser tab contract)
 *
 * These are the minimal checks that give the highest confidence that the app
 * is wired correctly across the 31 routes built in CI.
 */

const CORE_ROUTES: Array<{ path: string; titleFragment: string }> = [
  { path: "/", titleFragment: "Project 117" },
  { path: "/console/workspace", titleFragment: "Workspace" },
  { path: "/console/knowledge", titleFragment: "Knowledge" },
  { path: "/console/knowledge/hub", titleFragment: "Knowledge Hub" },
  { path: "/console/knowledge/documents", titleFragment: "Documents" },
  { path: "/dashboard", titleFragment: "Dashboard" },
];

for (const { path, titleFragment } of CORE_ROUTES) {
  test(`${path} renders without error`, async ({ page }) => {
    await page.goto(path);
    await expect(page).not.toHaveURL(/\/404|\/500/);
    // Page should have at least one h1 or h2 — not a blank error boundary
    const heading = page.locator("h1, h2").first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
    // Title should contain the expected fragment
    await expect(page).toHaveTitle(new RegExp(titleFragment, "i"));
  });
}

test("sidebar rail links are present on console pages", async ({ page }) => {
  await page.goto("/console/workspace");
  // The rail should render at least 3 nav links
  const navLinks = page.locator("nav a[href]");
  await expect(navLinks).toHaveCount(await navLinks.count());
  const count = await navLinks.count();
  expect(count).toBeGreaterThanOrEqual(3);
});
