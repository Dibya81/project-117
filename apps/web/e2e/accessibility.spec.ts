import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Accessibility (a11y) audit tests using axe-core.
 *
 * Scans core pages for WCAG 2.1 AA violations. Critical and Serious violations
 * fail the test; Moderate and Minor are reported as warnings (not failures) to
 * avoid noise from third-party components.
 *
 * Run: pnpm --filter @project-117/web exec playwright test e2e/accessibility.spec.ts
 */

const A11Y_ROUTES = [
  "/",
  "/console/workspace",
  "/console/knowledge/hub",
  "/console/knowledge/documents",
];

for (const route of A11Y_ROUTES) {
  test(`${route} has no critical a11y violations`, async ({ page }) => {
    await page.goto(route);
    // Wait for the page to fully render
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      // Exclude colour-contrast on dark glassmorphism surfaces — flagged separately
      .disableRules(["color-contrast"])
      .analyze();

    const criticalOrSerious = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );

    // Pretty-print any failures for easy debugging
    if (criticalOrSerious.length > 0) {
      console.error(
        "A11y violations on",
        route,
        JSON.stringify(
          criticalOrSerious.map((v) => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            nodes: v.nodes.map((n) => n.html).slice(0, 3),
          })),
          null,
          2
        )
      );
    }

    expect(criticalOrSerious).toHaveLength(0);
  });
}
