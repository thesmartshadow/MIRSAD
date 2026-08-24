import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const enabled = process.env.MIRSAD_V12_LIVE === "1";
const sessionId = process.env.MIRSAD_V12_SESSION_ID;
const skipActiveSearch = process.env.MIRSAD_V12_SKIP_ACTIVE === "1";
const liveBaseURL = process.env.MIRSAD_LIVE_BASE_URL ?? "";
const screenshotDirectory = path.resolve(
  process.cwd(),
  "../../reports/v1.2-ui-screenshots",
);
const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  test.skip(!enabled, "v1.2 operator-safe live validation is opt-in");
  if (!/^http:\/\/127\.0\.0\.1(?::\d+)?\/?$/.test(liveBaseURL)) {
    throw new Error("v1.2 live validation accepts only a local 127.0.0.1 origin");
  }
  if (!sessionId) throw new Error("MIRSAD_V12_SESSION_ID is required");
  fs.mkdirSync(screenshotDirectory, { recursive: true });
  const errors: string[] = [];
  browserErrors.set(page, errors);
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.addInitScript(() => {
    localStorage.setItem("mirsad.locale", "en");
    localStorage.setItem("mirsad.theme", "light");
  });
});

test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page) ?? []).toEqual([]);
});

async function captureRoute(page: Page, route: string, filename: string) {
  await page.goto(route);
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, {
    timeout: 15_000,
  });
  await page.screenshot({ path: path.join(screenshotDirectory, filename), fullPage: true });
}

test("v1.2 retrieval, coverage, route, and responsive evidence", async ({ page }) => {
  await captureRoute(page, "/search", "01-search-idle-light.png");
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByText("Dark", { exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.keyboard.press("Escape");
  await page.screenshot({
    path: path.join(screenshotDirectory, "01b-search-idle-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByText("Light", { exact: true }).click();

  if (!skipActiveSearch) {
    await page.getByLabel("Keyword or phrase").fill("بغداد");
    await page.getByRole("button", { name: "Run search" }).click();
    await expect(page.locator('[data-workspace-state="active"]')).toBeVisible();
    await page.screenshot({
      path: path.join(screenshotDirectory, "02-search-active.png"),
      fullPage: true,
    });
    await expect(page).toHaveURL(/\/search\/[0-9a-f-]{36}$/, { timeout: 45_000 });
  } else {
    await page.goto(`/search/${sessionId}`);
  }
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible({
    timeout: 15_000,
  });
  await page.screenshot({
    path: path.join(screenshotDirectory, "03-search-results.png"),
    fullPage: true,
  });

  await page.goto(`/search/${sessionId}`);
  await page.getByRole("tab", { name: "Retrieval coverage" }).click();
  await expect(
    page.getByRole("heading", { name: "What MIRSAD searched and could not search" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "04-coverage-overview.png"),
    fullPage: true,
  });
  await expect(page.getByRole("heading", { name: "Coverage gaps" })).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "05-coverage-gaps.png"),
    fullPage: true,
  });
  await expect(page.getByText("Local memory", { exact: true }).first()).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "06-local-memory-contribution.png"),
    fullPage: true,
  });
  await expect(page.getByText("Historical evidence", { exact: true }).first()).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "07-historical-evidence.png"),
    fullPage: true,
  });
  await expect(
    page.getByRole("heading", { name: "Why each source participated" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "08-why-this-source.png"),
    fullPage: true,
  });

  await page.getByRole("tab", { name: "Results" }).click();
  const explain = page.getByRole("button", { name: "Explain score" }).first();
  if (await explain.isVisible()) {
    await explain.click();
    await page.screenshot({
      path: path.join(screenshotDirectory, "09-explain-score.png"),
      fullPage: true,
    });
    await page.keyboard.press("Escape");
  }

  for (const [route, filename] of [
    ["/analytics", "10-analytics.png"],
    ["/clusters", "11-clusters.png"],
    ["/compare", "12-compare.png"],
    ["/history", "13-history.png"],
    ["/saved", "14-saved-searches.png"],
    ["/bookmarks", "15-bookmarks.png"],
    ["/sources", "16-sources.png"],
    ["/system", "17-system.png"],
    ["/settings", "18-settings.png"],
  ]) {
    await captureRoute(page, route, filename);
  }

  await page.goto(`/search/${sessionId}`);
  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByRole("tab", { name: "تغطية الاسترجاع" }).click();
  await page.screenshot({
    path: path.join(screenshotDirectory, "19-arabic-rtl.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: path.join(screenshotDirectory, "20-mobile.png"),
    fullPage: true,
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0);
  await page.screenshot({
    path: path.join(screenshotDirectory, "21-reduced-motion.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.goto(`/search/${sessionId}?webgl=off`);
  await page.getByTestId("trace-toggle").click();
  await expect(page.getByTestId("webgl-fallback")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await page.screenshot({
    path: path.join(screenshotDirectory, "22-webgl-fallback.png"),
    fullPage: true,
  });
});
