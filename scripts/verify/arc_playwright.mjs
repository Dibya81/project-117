/**
 * Agent Response Console — DOM-level end-to-end proof.
 *
 * Drives the real backend on :8004 through the real console on :3018 and
 * asserts the three lanes fill from real events, the failover highlight comes
 * from the payload's `related_equipment_id`, the Verified badge appears only
 * after verification, the no-response state appears on a genuinely stalled
 * step, and the mock banner appears only after the stream fails three times
 * (and clears only on a fresh connection).
 *
 * Run:
 *   node scripts/verify/arc_playwright.mjs
 *
 * Playwright is the globally installed copy named in the task.
 */
import { chromium } from "/Users/dibyabhusal/.local/share/fnm/node-versions/v22.23.1/installation/lib/node_modules/playwright/index.mjs";

const WEB = process.env.ARC_WEB ?? "http://127.0.0.1:3018";
const PLANT = process.env.ARC_PLANT ?? "refinery";

let passed = 0;
let failed = 0;
const failures = [];

function check(name, condition, detail = "") {
  if (condition) {
    passed += 1;
    console.log(`  PASS  ${name}${detail ? ` — ${detail}` : ""}`);
  } else {
    failed += 1;
    failures.push(name);
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  }
}

async function injectFault(page, unit, modeName) {
  await page.waitForSelector(`[data-unit="${unit}"]`, { timeout: 20_000 });
  await page.locator(`[data-unit="${unit}"]`).first().click();
  // The rail shows the selected asset's declared failure modes.
  const injected = page.waitForResponse(
    (r) => r.url().includes(`/equipment/${unit}/failure`) && r.request().method() === "POST",
    { timeout: 15_000 },
  );
  await page.getByRole("button", { name: modeName, exact: true }).first().click();
  const resp = await injected;
  const body = await resp.json().catch(() => ({}));
  return body?.incident?.id ?? null;
}

async function testHappyPath(browser) {
  console.log("\n[1] Real flow — sensor failure on P-1042");
  const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`    [browser error] ${m.text()}`);
  });
  await page.goto(`${WEB}/console/simulation/plant/${PLANT}`, { waitUntil: "domcontentloaded" });

  const incidentId = await injectFault(page, "e-P-1042", "Sensor failure");
  check("backend returned an incident id for the job", Boolean(incidentId), incidentId ?? "none");

  await page.waitForSelector('[data-testid="agent-response-console"][data-open="true"]', { timeout: 20_000 });
  check("console docks open after injection", true);

  // --- LANE A -------------------------------------------------------------
  await page.waitForSelector('[data-testid="lane-a"]', { timeout: 20_000 });
  const laneA = {
    equipment: await page.locator('[data-testid="lane-a-equipment"]').textContent(),
    fault: await page.locator('[data-testid="lane-a-fault"]').textContent(),
    severity: await page.locator('[data-testid="lane-a-severity"]').textContent(),
  };
  check("lane A shows equipment tag from payload", laneA.equipment?.trim() === "P-1042", laneA.equipment ?? "");
  check("lane A shows fault type from payload", laneA.fault?.trim() === "Sensor failure", laneA.fault ?? "");
  check("lane A shows severity from payload", laneA.severity?.trim() === "warning", laneA.severity ?? "");
  const handoffVisible = await page
    .waitForSelector('[data-testid="lane-a-handoff"]', { timeout: 10_000 })
    .then(() => true)
    .catch(() => false);
  check("lane A shows routing line once handoff is indicated", handoffVisible);
  await page.waitForSelector('[data-testid="lane-a"][data-complete="true"]', { timeout: 10_000 });
  check("lane A greys out once BOTH lanes have started", true);

  // --- LANE B -------------------------------------------------------------
  const stepState = (id) => page.locator(`[data-step="${id}"]`).getAttribute("data-state");
  await page.waitForSelector('[data-step="b-failover-done"][data-state="done"]', { timeout: 15_000 });
  check("lane B notified step completed", (await stepState("b-notified")) === "done");
  check("lane B failover evaluating step completed", (await stepState("b-failover-eval")) === "done");
  const failoverLabel = await page.locator('[data-step="b-failover-done"] .arc-step__label').textContent();
  const failoverDetail = await page.locator('[data-step="b-failover-done"] .arc-step__detail').textContent();
  check("lane B switch step names the replacement from the payload", /PT-1103/.test(failoverLabel ?? ""), failoverLabel ?? "");
  check("lane B switch step carries the related equipment id", /e-V-1103/.test(failoverDetail ?? ""), failoverDetail ?? "");

  // --- canvas: failover highlight driven by related_equipment_id -----------
  const highlighted = await page
    .locator('[data-unit="e-V-1103"][data-failover-target="true"]')
    .count();
  check("canvas highlights the replacement equipment (blue glow target)", highlighted === 1, `count=${highlighted}`);
  const link = await page.locator('[data-testid="failover-link"]').first().getAttribute("data-to");
  check("canvas draws the failover link to the payload's equipment", link === "e-V-1103", link ?? "");
  const linkPath = await page.locator('[data-testid="failover-link"] .arc-failover-link').count();
  check("failover link has an animated connection path", linkPath === 1);

  // --- LANE C -------------------------------------------------------------
  await page.waitForSelector('[data-step="c-notify"][data-state="done"]', { timeout: 15_000 });
  check("lane C history step completed", (await stepState("c-history")) === "done");
  check("lane C root-cause step completed", (await stepState("c-root")) === "done");
  check("lane C prediction step completed", (await stepState("c-prediction")) === "done");
  const rootMode = await page.locator('[data-testid="root-cause-mode"]').textContent();
  check("root cause names a declared failure mode", /sensor_failure/.test(rootMode ?? ""), rootMode ?? "");
  const predCount = await page.locator('[data-testid="prediction-item"]').count();
  check("prediction lists 2-3 ranked candidates", predCount === 3, `count=${predCount}`);
  const firstPrediction = await page.locator('[data-testid="prediction-item"]').first().getAttribute("data-equipment");
  await page.locator('[data-testid="prediction-item"]').first().click();
  await page.waitForSelector(`[data-unit="${firstPrediction}"][data-predicted="true"]`, { timeout: 8000 });
  check(
    "clicking a prediction highlights it on the canvas in amber",
    (await page.locator(`[data-unit="${firstPrediction}"][data-predicted="true"]`).count()) === 1,
    firstPrediction ?? "",
  );
  check("user notification text is present", (await page.locator('[data-testid="user-notice"]').count()) === 1);

  // --- VERIFIED badge -----------------------------------------------------
  const before = await page.locator('[data-testid="verified-badge"]').getAttribute("data-visible");
  check("verified badge is hidden before verification", before === "false", before ?? "");
  await page.locator('.sm-plan button:has-text("Approve")').first().click();
  await page.waitForSelector('[data-testid="verified-badge"][data-visible="true"]', { timeout: 25_000 });
  const verifiedText = await page.locator('[data-testid="verified-badge"]').textContent();
  check("verified badge appears after verification.completed", true);
  check("verified badge reads as an independent check", /independent check/.test(verifiedText ?? ""), verifiedText ?? "");

  await page.screenshot({ path: "/tmp/arc-happy.png", fullPage: false });
  await page.close();
}

async function testNoResponse(browser) {
  console.log("\n[2] No-response — trip on P-1042 has no redundant measurement");
  const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
  await page.goto(`${WEB}/console/simulation/plant/${PLANT}?stepTimeout=1500`, {
    waitUntil: "domcontentloaded",
  });
  await injectFault(page, "e-P-1042", "Equipment trip");
  await page.waitForSelector('[data-testid="agent-response-console"][data-open="true"]', { timeout: 20_000 });

  // The ops lane starts evaluating and never receives a completion event.
  await page.waitForSelector('[data-step="b-failover-eval"][data-state="active"]', { timeout: 15_000 });
  check("stalled step first shows the pulsing in-progress state", true);
  await page.waitForSelector('[data-step="b-failover-eval"][data-state="stalled"]', { timeout: 8000 });
  const noResponse = await page.locator('[data-step="b-failover-eval"] [data-testid="no-response"]').textContent();
  check("no-response state appears on the stalled step", /no response from orchestrator/.test(noResponse ?? ""), noResponse ?? "");
  check(
    "neither the stalled step nor the lane was fake-completed",
    (await page.locator('[data-step="b-failover-done"][data-state="pending"]').count()) === 1,
  );
  await page.screenshot({ path: "/tmp/arc-no-response.png" });
  await page.close();
}

async function testMockBanner(browser) {
  console.log("\n[3] Mock mode — stream fails 3 times");
  const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
  let aborting = true;
  await page.route("**/api/simulation/plants/*/stream*", (route) => {
    if (aborting) void route.abort();
    else void route.continue();
  });
  await page.goto(`${WEB}/console/simulation/plant/${PLANT}`, { waitUntil: "domcontentloaded" });
  // Injection itself uses REST, which is not blocked — only the SSE stream is.
  await injectFault(page, "e-P-1042", "Sensor failure");
  await page.waitForSelector('[data-testid="agent-response-console"][data-open="true"]', { timeout: 20_000 });
  await page.waitForSelector('[data-testid="mock-mode-banner"]', { timeout: 15_000 });
  check("mock banner appears after three failed stream attempts", true);

  // The local development sequence runs; a real-looking event must not clear it.
  await page.waitForSelector('[data-testid="lane-a"]', { timeout: 10_000 });
  await page.waitForTimeout(3000);
  check(
    "banner is never cleared by an event",
    await page.locator('[data-testid="mock-mode-banner"]').isVisible(),
  );

  // A fresh successful connection is the only thing that clears it.
  aborting = false;
  await page.waitForSelector('[data-testid="mock-mode-banner"]', { state: "detached", timeout: 30_000 });
  check("banner clears on a fresh successful connection", true);
  await page.close();
}

const browser = await chromium.launch();
try {
  await testHappyPath(browser);
  await testNoResponse(browser);
  await testMockBanner(browser);
} finally {
  await browser.close();
}

console.log(`\n${passed} passed, ${failed} failed`);
if (failed) {
  console.log("Failed assertions:", failures.join("; "));
  process.exit(1);
}
