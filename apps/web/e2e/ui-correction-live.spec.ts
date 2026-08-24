import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const enabled = process.env.MIRSAD_UI_CORRECTION_LIVE === "1";
const sessionId = process.env.MIRSAD_LAYOUT_SESSION_ID;
const liveBaseURL = process.env.MIRSAD_LIVE_BASE_URL ?? "";
const outputDirectory = path.resolve(
  process.env.MIRSAD_UI_CORRECTION_DIR ??
    path.join(process.cwd(), "../../reports/mirsad-v1.2-ui-correction-screenshots"),
);

const viewports = [
  { width: 1920, height: 1080 },
  { width: 1600, height: 900 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 430, height: 932 },
  { width: 390, height: 844 },
] as const;

const routes = [
  ["/analytics", "analytics"],
  ["/compare", "compare"],
  ["/history", "history"],
  ["/saved", "saved"],
  ["/bookmarks", "bookmarks"],
  ["/sources", "sources"],
  ["/system", "system"],
  ["/settings", "settings"],
] as const;

async function waitForPage(page: Page) {
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator(".instrument-command-layer")).toBeVisible();
  await expect(page.locator(".instrument-page-header")).toBeVisible();
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, {
    timeout: 20_000,
  });
}

async function openClusters(page: Page) {
  const desktopLink = page.locator('nav a[href="/clusters"]:visible').first();
  if (await desktopLink.isVisible()) {
    await desktopLink.click();
  } else {
    await page.locator('[data-navigation-menu="trigger"]:visible').click();
    await page.locator('.route-drawer a[href="/clusters"]').click();
  }
  await expect(page).toHaveURL(/\/clusters$/);
  await waitForPage(page);
  if (await page.locator(".route-drawer").count()) {
    await page.keyboard.press("Escape");
    await expect(page.locator(".route-drawer")).toHaveCount(0);
  }
}

async function layoutIssues(page: Page, route: string) {
  return page.evaluate((routeName) => {
    const issues: string[] = [];
    const viewportWidth = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > viewportWidth + 1) {
      issues.push(
        `document-overflow:${document.documentElement.scrollWidth - viewportWidth}px`,
      );
    }

    const appHeader = document.querySelector<HTMLElement>(
      ".instrument-command-layer",
    );
    const pageHeader = document.querySelector<HTMLElement>(
      ".instrument-page-header",
    );
    if (appHeader && pageHeader) {
      const appRect = appHeader.getBoundingClientRect();
      const pageRect = pageHeader.getBoundingClientRect();
      if (pageRect.top < appRect.bottom + 12) {
        issues.push(
          `page-header-under-navigation:${Math.round(pageRect.top)}<${Math.round(appRect.bottom)}`,
        );
      }
      const title = pageHeader.querySelector("h2")?.getBoundingClientRect();
      if (title && (title.top < pageRect.top || title.bottom > pageRect.bottom + 1)) {
        issues.push("page-title-clipped");
      }
    }

    for (const element of document.querySelectorAll<HTMLElement>(
      ".instrument-page-header, [data-search-instrument], .history-ledger, .collection-ledger, .settings-plane",
    )) {
      const rect = element.getBoundingClientRect();
      if (rect.left < -1 || rect.right > viewportWidth + 1) {
        issues.push(
          `${routeName}-primary-outside:${element.className}:${Math.round(rect.left)}..${Math.round(rect.right)}`,
        );
      }
    }

    return issues;
  }, route);
}

test("operator routes keep a stable shell, interaction, and bidi layout", async ({
  page,
}) => {
  test.skip(!enabled, "UI correction validation is opt-in");
  test.setTimeout(360_000);
  if (!/^http:\/\/127\.0\.0\.1(?::\d+)?\/?$/.test(liveBaseURL)) {
    throw new Error("UI correction validation accepts only a local origin");
  }
  if (!sessionId) throw new Error("MIRSAD_LAYOUT_SESSION_ID is required");
  fs.mkdirSync(outputDirectory, { recursive: true });

  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));

  const issues: string[] = [];
  for (const locale of ["en", "ar"] as const) {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.goto(`/search/${sessionId}`);
      await page.evaluate((nextLocale) => {
        localStorage.setItem("mirsad.locale", nextLocale);
        localStorage.setItem("mirsad.theme", "light");
      }, locale);
      await page.reload();
      await waitForPage(page);

      const prefix = `${locale}-${viewport.width}x${viewport.height}`;
      issues.push(
        ...(await layoutIssues(page, "search")).map(
          (issue) => `${prefix}:search:${issue}`,
        ),
      );
      await page.screenshot({
        path: path.join(outputDirectory, `${prefix}-search.png`),
      });

      await openClusters(page);
      issues.push(
        ...(await layoutIssues(page, "clusters")).map(
          (issue) => `${prefix}:clusters:${issue}`,
        ),
      );
      await page.screenshot({
        path: path.join(outputDirectory, `${prefix}-clusters.png`),
      });

      for (const [routePath, routeName] of routes) {
        await page.goto(routePath);
        await waitForPage(page);
        issues.push(
          ...(await layoutIssues(page, routeName)).map(
            (issue) => `${prefix}:${routeName}:${issue}`,
          ),
        );
        await page.screenshot({
          path: path.join(outputDirectory, `${prefix}-${routeName}.png`),
        });
      }

      const runtime = page.getByText(
        locale === "ar" ? "على الجهاز" : "ON-DEVICE",
        { exact: true },
      );
      if (!(await runtime.isVisible().catch(() => false))) {
        issues.push(`${prefix}:settings:runtime-indicator-missing`);
      }
      const menuButton = page.locator('[data-navigation-menu="trigger"]:visible');
      if (!(await menuButton.isVisible().catch(() => false))) {
        issues.push(`${prefix}:settings:navigation-menu-missing`);
      } else {
        await menuButton.click();
        const content = page.locator('[data-navigation-menu="content"]:visible');
        const opened = await expect(content).toBeVisible({ timeout: 2_000 }).then(
          () => true,
          () => false,
        );
        if (!opened) {
          issues.push(`${prefix}:settings:navigation-menu-did-not-open`);
        }
        const expanded = await expect(menuButton)
          .toHaveAttribute("aria-expanded", "true", { timeout: 2_000 })
          .then(() => true, () => false);
        if (!expanded) {
          issues.push(`${prefix}:settings:navigation-menu-aria-expanded`);
        }
        if (opened) {
          await content.press("Escape");
          await expect(page.locator('[data-navigation-menu="content"]:visible')).toHaveCount(0);
          if (locale === "en" && viewport.width === 1920) {
            await menuButton.click();
            await expect(page.locator('[data-navigation-menu="content"]:visible')).toBeVisible();
            await menuButton.click();
            await expect(page.locator('[data-navigation-menu="content"]:visible')).toHaveCount(0);
            await menuButton.click();
            await expect(page.locator('[data-navigation-menu="content"]:visible')).toBeVisible();
            await page.mouse.click(10, 200);
            await expect(page.locator('[data-navigation-menu="content"]:visible')).toHaveCount(0);
          }
        }
      }
    }
  }

  expect(errors).toEqual([]);
  expect(issues).toEqual([]);
});
