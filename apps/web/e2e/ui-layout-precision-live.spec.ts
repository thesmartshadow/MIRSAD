import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const enabled = process.env.MIRSAD_LAYOUT_LIVE === "1";
const sessionId = process.env.MIRSAD_LAYOUT_SESSION_ID;
const liveBaseURL = process.env.MIRSAD_LIVE_BASE_URL ?? "";
const outputDirectory = path.resolve(
  process.env.MIRSAD_LAYOUT_AUDIT_DIR ??
    path.join(process.cwd(), "../../reports/ui-layout-fix-screenshots"),
);

const viewports = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
] as const;

const routes = [
  ["/analytics", "analytics"],
  ["/compare", "compare"],
  ["/history", "history"],
  ["/sources", "sources"],
  ["/system", "system"],
] as const;

async function waitForPage(page: Page) {
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, {
    timeout: 20_000,
  });
  await expect(page.locator("main")).toBeVisible();
}

async function openClusters(page: Page) {
  const desktopLink = page.locator('nav.route-aperture a[href="/clusters"]');
  if (await desktopLink.isVisible()) {
    await desktopLink.click();
  } else {
    await page.locator('[data-navigation-menu="trigger"]:visible').click();
    await page.locator('.route-drawer a[href="/clusters"]').click();
    await page.keyboard.press("Escape");
    await expect(page.locator(".route-drawer")).toHaveCount(0);
  }
  await expect(page).toHaveURL(/\/clusters$/);
  await waitForPage(page);
}

async function geometryIssues(page: Page, route: string) {
  return page.evaluate((currentRoute) => {
    const issues: string[] = [];
    const root = document.documentElement;
    if (root.scrollWidth > root.clientWidth + 1) {
      issues.push(`document-overflow:${root.scrollWidth - root.clientWidth}px`);
    }

    const overlaps = (left: DOMRect, right: DOMRect, inset = 0) =>
      left.left + inset < right.right - inset &&
      left.right - inset > right.left + inset &&
      left.top + inset < right.bottom - inset &&
      left.bottom - inset > right.top + inset;

    if (currentRoute === "sources") {
      const svg = document.querySelector<SVGSVGElement>(
        ".source-capability-space svg",
      );
      const labels = [
        ...document.querySelectorAll<SVGTextElement>(".source-topology__label"),
      ];
      const nodes = [
        ...document.querySelectorAll<SVGCircleElement>(
          ".source-topology__node",
        ),
      ];
      if (svg) {
        const svgRect = svg.getBoundingClientRect();
        labels.forEach((label, index) => {
          const rect = label.getBoundingClientRect();
          if (
            rect.left < svgRect.left - 1 ||
            rect.right > svgRect.right + 1 ||
            rect.top < svgRect.top - 1 ||
            rect.bottom > svgRect.bottom + 1
          ) {
            issues.push(`source-label-outside:${label.textContent}`);
          }
          labels.slice(index + 1).forEach((other) => {
            if (overlaps(rect, other.getBoundingClientRect(), 1)) {
              issues.push(
                `source-label-collision:${label.textContent}|${other.textContent}`,
              );
            }
          });
          nodes.forEach((node) => {
            if (node.parentElement === label.parentElement) return;
            if (overlaps(rect, node.getBoundingClientRect(), 1)) {
              issues.push(
                `source-label-node:${label.textContent}|${node.parentElement?.getAttribute("aria-label")}`,
              );
            }
          });
        });
      }
    }

    if (currentRoute === "clusters") {
      const svg = document.querySelector<SVGSVGElement>(".cluster-field svg");
      const nodes = [
        ...document.querySelectorAll<SVGGElement>(".cluster-field__node"),
      ];
      nodes.forEach((node, index) => {
        const rect = node.getBoundingClientRect();
        const center = {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        };
        const radius = Math.max(rect.width, rect.height) / 2;
        const count = node.querySelector<SVGTextElement>(
          ".cluster-field__count",
        );
        const body = node.querySelector<SVGCircleElement>(".cluster-field__point");
        if (svg) {
          const svgRect = svg.getBoundingClientRect();
          if (
            rect.left < svgRect.left - 1 ||
            rect.right > svgRect.right + 1 ||
            rect.top < svgRect.top - 1 ||
            rect.bottom > svgRect.bottom + 1
          ) {
            issues.push(
              `cluster-node-outside:${node.getAttribute("aria-label")}`,
            );
          }
        }
        if (count && body) {
          const countRect = count.getBoundingClientRect();
          const bodyRect = body.getBoundingClientRect();
          if (
            countRect.left < bodyRect.left + 2 ||
            countRect.right > bodyRect.right - 2 ||
            countRect.top < bodyRect.top + 2 ||
            countRect.bottom > bodyRect.bottom - 2
          ) {
            issues.push(`cluster-count-outside:${count.textContent}`);
          }
        }
        nodes.slice(index + 1).forEach((other) => {
          const otherRect = other.getBoundingClientRect();
          const otherCenter = {
            x: otherRect.left + otherRect.width / 2,
            y: otherRect.top + otherRect.height / 2,
          };
          const otherRadius = Math.max(otherRect.width, otherRect.height) / 2;
          if (
            Math.hypot(center.x - otherCenter.x, center.y - otherCenter.y) <
            radius + otherRadius + 2
          ) {
            issues.push(
              `cluster-node-collision:${node.getAttribute("aria-label")}|${other.getAttribute("aria-label")}`,
            );
          }
        });
      });
    }

    return issues;
  }, route);
}

test("major routes remain collision-free across the viewport and locale matrix", async ({
  page,
}) => {
  test.skip(!enabled, "precision layout validation is opt-in");
  test.setTimeout(240_000);
  if (!/^http:\/\/127\.0\.0\.1(?::\d+)?\/?$/.test(liveBaseURL)) {
    throw new Error("Layout validation accepts only a local 127.0.0.1 origin");
  }
  if (!sessionId) throw new Error("MIRSAD_LAYOUT_SESSION_ID is required");
  fs.mkdirSync(outputDirectory, { recursive: true });

  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  const allIssues: string[] = [];
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
      allIssues.push(
        ...(await geometryIssues(page, "search")).map(
          (issue) => `${prefix}:search:${issue}`,
        ),
      );
      await page.screenshot({
        path: path.join(outputDirectory, `${prefix}-search.png`),
      });

      await openClusters(page);
      allIssues.push(
        ...(await geometryIssues(page, "clusters")).map(
          (issue) => `${prefix}:clusters:${issue}`,
        ),
      );
      await page.screenshot({
        path: path.join(outputDirectory, `${prefix}-clusters.png`),
      });

      for (const [routePath, routeName] of routes) {
        await page.goto(routePath);
        await waitForPage(page);
        allIssues.push(
          ...(await geometryIssues(page, routeName)).map(
            (issue) => `${prefix}:${routeName}:${issue}`,
          ),
        );
        await page.screenshot({
          path: path.join(outputDirectory, `${prefix}-${routeName}.png`),
        });
      }
    }
  }

  expect(consoleErrors).toEqual([]);
  expect(allIssues).toEqual([]);
});
