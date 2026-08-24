import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const enabled = process.env.MIRSAD_FINAL_UI_LIVE === "1";
const runActive = process.env.MIRSAD_FINAL_UI_ACTIVE === "1";
const seedSessionId = process.env.MIRSAD_FINAL_UI_SESSION_ID;
const liveBaseURL = process.env.MIRSAD_LIVE_BASE_URL ?? "";
const screenshotDirectory = path.resolve(process.cwd(), "../../reports/v1.2-final-ui-screenshots");
const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  test.skip(!enabled, "final UI live validation is opt-in");
  if (!/^http:\/\/127\.0\.0\.1(?::\d+)?\/?$/.test(liveBaseURL)) {
    throw new Error("Final UI validation accepts only a local 127.0.0.1 origin");
  }
  if (!seedSessionId) throw new Error("MIRSAD_FINAL_UI_SESSION_ID is required");
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

async function shot(page: Page, name: string, fullPage = false) {
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, { timeout: 20_000 });
  await page.screenshot({ path: path.join(screenshotDirectory, name), fullPage });
}

async function route(page: Page, pathName: string, label: string, name: string, fullPage = false) {
  const primary = page.locator("nav.route-aperture").getByRole("link", { name: label, exact: true });
  if (await primary.isVisible().catch(() => false)) {
    await primary.click();
  } else {
    await page.locator('[data-navigation-menu="trigger"]:visible').click();
    await page.locator(`[data-navigation-menu="content"] a[href="${pathName}"]`).click();
  }
  await expect(page).toHaveURL(new RegExp(`${pathName}$`));
  await expect(page.locator(`.instrument-page--${pathName.slice(1)}`)).toBeVisible();
  await shot(page, name, fullPage);
}

test("complete v1.2 final visual system", async ({ page }) => {
  await page.goto("/search");
  await shot(page, "01-search-idle-light.png");
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByText("Dark", { exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await shot(page, "02-search-idle-dark.png");
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByText("Light", { exact: true }).click();

  let sessionId = seedSessionId!;
  if (runActive) {
    await page.getByLabel("Keyword or phrase").fill("OpenAI");
    await page.getByRole("button", { name: "Run search" }).click();
    await expect(page.locator('[data-workspace-state="active"]')).toBeVisible();
    await page.screenshot({ path: path.join(screenshotDirectory, "03-search-active.png") });
    await expect(page).toHaveURL(/\/search\/[0-9a-f-]{36}$/, { timeout: 60_000 });
    sessionId = page.url().split("/").pop()!;
  } else {
    await page.goto(`/search/${sessionId}`);
  }

  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible({ timeout: 20_000 });
  await shot(page, "04-search-results.png");
  await page.getByRole("tab", { name: "Retrieval coverage" }).click();
  await shot(page, "05-coverage.png", true);
  await page.getByRole("tab", { name: "Results" }).click();
  const explain = page.getByRole("button", { name: "Explain score" }).first();
  if (await explain.isVisible()) {
    await explain.click();
    await shot(page, "06-explain-score.png");
    await page.keyboard.press("Escape");
  }

  await route(page, "/analytics", "Analytics", "07-analytics.png");
  await route(page, "/clusters", "Clusters", "08-clusters.png");
  await route(page, "/compare", "Compare", "09-compare.png");
  const compareButton = page.getByRole("button", { name: "Compare collections" });
  if (await compareButton.isEnabled()) {
    await compareButton.click();
    await expect(page.locator(".compare-plane")).toBeVisible();
    await shot(page, "09-compare.png");
  }
  await route(page, "/history", "History", "10-history.png");
  await route(page, "/saved", "Saved Searches", "11-saved-searches.png");
  await route(page, "/bookmarks", "Bookmarks", "12-bookmarks.png");
  await route(page, "/sources", "Sources", "13-sources.png");
  await route(page, "/system", "System", "14-system.png");
  await route(page, "/settings", "Settings", "15-settings.png");

  await page.goto(`/search/${sessionId}`);
  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await shot(page, "16-arabic-rtl-results.png");

  await page.setViewportSize({ width: 390, height: 844 });
  await shot(page, "17-mobile-results.png");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible({ timeout: 20_000 });
  await shot(page, "18-reduced-motion.png");

  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.goto(`/search/${sessionId}?webgl=off`);
  await page.getByTestId("trace-toggle").click();
  await expect(page.getByTestId("webgl-fallback")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await shot(page, "19-webgl-fallback.png");
});
