import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration.
 *
 * Targets the Next.js dev server at http://localhost:3017.
 * The web server is started automatically before tests run and torn down after.
 *
 * Run locally:   pnpm --filter @project-117/web exec playwright test
 * Run headed:    pnpm --filter @project-117/web exec playwright test --headed
 * Debug:         pnpm --filter @project-117/web exec playwright test --debug
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { outputFolder: "playwright-report" }]],
  use: {
    baseURL: "http://localhost:3017",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3017",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
