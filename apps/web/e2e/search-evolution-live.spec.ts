import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const enabled = process.env.MIRSAD_EVOLUTION_LIVE === "1";
const completedSession = process.env.MIRSAD_EVOLUTION_SESSION_ID;
const partialSession = process.env.MIRSAD_EVOLUTION_PARTIAL_SESSION_ID;
const screenshotDirectory = path.resolve(
  process.cwd(),
  "../../reports/search-evolution-screenshots",
);

const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  test.skip(!enabled, "Production search-evolution validation is opt-in");
  const errors: string[] = [];
  browserErrors.set(page, errors);
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
});

test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page) ?? []).toEqual([]);
});

test("real search workspace streams, stabilizes, and remains responsive", async ({
  page,
}) => {
  test.skip(!completedSession || !partialSession, "Live session evidence not supplied");

  await page.goto("/search");
  await expect(page.getByLabel("Keyword or phrase")).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "desktop-idle-search.png"),
    fullPage: true,
  });

  await page.getByLabel("Keyword or phrase").fill("#بغداد");
  await page.getByRole("button", { name: "Run search" }).click();
  await expect(
    page.locator('div[aria-live="polite"][aria-busy="true"]'),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "desktop-active-live-search.png"),
    fullPage: true,
  });
  await expect(page).toHaveURL(/\/search\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  await expect(page.getByText("Results", { exact: true }).first()).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "desktop-completed-results.png"),
    fullPage: true,
  });

  const explain = page.getByRole("button", { name: "Explain score" }).first();
  if (await explain.isVisible()) {
    await explain.click();
    await expect(
      page.getByText("Deterministic signals used for this ranking"),
    ).toBeVisible();
    await page.screenshot({
      path: path.join(screenshotDirectory, "result-explain-score.png"),
      fullPage: true,
    });
    await page.keyboard.press("Escape");
  }

  await page.getByRole("tab", { name: "Clusters" }).click();
  await expect(page.getByRole("tabpanel")).toBeVisible();
  await page.getByRole("tab", { name: "Timeline" }).click();
  await expect(page.getByRole("tabpanel")).toBeVisible();
  await page.getByRole("tab", { name: "Analytics" }).click();
  await expect(page.getByRole("tabpanel")).toBeVisible();

  await page.goto(`/search/${partialSession}`);
  await expect(page.getByText("Partial coverage")).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "partial-search.png"),
    fullPage: true,
  });

  await page.goto(`/search/${completedSession}`);
  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.screenshot({
    path: path.join(screenshotDirectory, "arabic-rtl.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('main[data-slot="sidebar-inset"]')).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "mobile-narrow-search.png"),
    fullPage: true,
  });
});
