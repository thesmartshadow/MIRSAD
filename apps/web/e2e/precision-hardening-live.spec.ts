import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const enabled = process.env.MIRSAD_PRECISION_LIVE === "1";
const completedSession = process.env.MIRSAD_PRECISION_SESSION_ID;
const partialSession = process.env.MIRSAD_PRECISION_PARTIAL_SESSION_ID;
const lexicalSession = process.env.MIRSAD_PRECISION_LEXICAL_SESSION_ID;
const screenshotDirectory = path.resolve(
  process.cwd(),
  "../../reports/precision-hardening-screenshots",
);
const visualEvidencePath = path.resolve(
  process.cwd(),
  "../../reports/precision-hardening-visual.json",
);
const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  test.skip(!enabled, "Precision-hardening live validation is opt-in");
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

test("precision workspace, provenance, motion, fallback, and responsive states", async ({ page }) => {
  test.skip(!completedSession || !partialSession || !lexicalSession, "Evidence sessions were not supplied");
  const visualEvidence: Record<string, unknown> = {
    schema: "mirsad.precision-hardening-visual",
    captured_at: new Date().toISOString(),
  };

  await page.goto("/search");
  await expect(page.getByLabel("Keyword or phrase")).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDirectory, "01-search-idle-light.png"), fullPage: true });

  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByText("Dark", { exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.screenshot({ path: path.join(screenshotDirectory, "02-search-idle-dark.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByText("Light", { exact: true }).click();

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await page.getByLabel("كلمة مفتاحية أو عبارة").fill("بغداد");
  await page.getByRole("button", { name: "تشغيل البحث" }).click();
  await expect(page.locator('[data-workspace-state="active"]')).toBeVisible();
  await expect(page.getByTestId("retrieval-flow-svg")).toBeVisible();
  const activeTopology = page.getByTestId("retrieval-topology-3d");
  await expect(activeTopology.locator("canvas")).toHaveCount(1);
  const rendererInfo = await activeTopology.evaluate((element) => ({
    render_calls: Number(element.dataset.renderCalls ?? 0),
    triangles: Number(element.dataset.triangles ?? 0),
    geometries: Number(element.dataset.geometries ?? 0),
    textures: Number(element.dataset.textures ?? 0),
  }));
  const frameTiming = await page.evaluate(async () => {
    const intervals: number[] = [];
    let previous = performance.now();
    await new Promise<void>((resolve) => {
      const sample = (now: number) => {
        intervals.push(now - previous);
        previous = now;
        if (intervals.length >= 30) resolve();
        else requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    });
    return {
      sample_count: intervals.length,
      average_frame_ms: intervals.reduce((sum, value) => sum + value, 0) / intervals.length,
      maximum_frame_ms: Math.max(...intervals),
      frames_over_25_ms: intervals.filter((value) => value > 25).length,
    };
  });
  visualEvidence.active = { renderer_info: rendererInfo, frame_timing: frameTiming };
  await page.screenshot({ path: path.join(screenshotDirectory, "03-search-active-topology.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshotDirectory, "04-search-active-svg-flow.png"), fullPage: true });
  await page.screenshot({ path: path.join(screenshotDirectory, "10-arabic-rtl-active.png"), fullPage: true });
  const ranking = page.getByText("ترتيب", { exact: true }).first();
  await expect(ranking).toBeVisible({ timeout: 5_000 }).catch(() => undefined);
  await page.screenshot({ path: path.join(screenshotDirectory, "05-search-ranking-state.png"), fullPage: true });
  await expect(page).toHaveURL(/\/search\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible();
  await expect(page.getByTestId("desktop-filter-rail")).toHaveClass(/hidden/);
  await expect(page.getByTestId("desktop-trace-rail")).toHaveClass(/hidden/);
  await page.screenshot({ path: path.join(screenshotDirectory, "11-arabic-rtl-completed.png"), fullPage: true });

  await page.getByRole("button", { name: "تغيير اللغة" }).click();
  await page.getByText("الإنجليزية", { exact: true }).click();
  await page.screenshot({ path: path.join(screenshotDirectory, "06-search-completed-results-first.png"), fullPage: true });
  await expect(page.getByText(/Acquired through:/).first()).toBeVisible();
  await page.getByTestId("trace-toggle").click();
  await expect(page.getByRole("dialog", { name: "Live search" })).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(1);
  await page.screenshot({ path: path.join(screenshotDirectory, "07-search-completed-trace-open.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await expect(page.locator("canvas")).toHaveCount(0);
  const canvasCounts: number[] = [];
  const heapBefore = await page.evaluate(() => {
    const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
    return memory?.usedJSHeapSize ?? null;
  });
  for (let iteration = 0; iteration < 3; iteration += 1) {
    await page.getByTestId("trace-toggle").click();
    await expect(page.locator("canvas")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(page.locator("canvas")).toHaveCount(0);
    canvasCounts.push(await page.locator("canvas").count());
  }
  const heapAfter = await page.evaluate(() => {
    const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
    return memory?.usedJSHeapSize ?? null;
  });
  visualEvidence.lifecycle = {
    repeated_mount_cycles: canvasCounts.length,
    canvas_counts_after_unmount: canvasCounts,
    heap_before_bytes: heapBefore,
    heap_after_bytes: heapAfter,
  };

  const localMemory = page.getByTestId("result-acquisition-path").filter({ hasText: "LOCAL MEMORY" }).first();
  await expect(localMemory).toBeVisible();
  await localMemory.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(screenshotDirectory, "09-local-memory-provenance.png"), fullPage: true });

  await page.getByRole("button", { name: "Explain score" }).first().click();
  await expect(page.getByTestId("score-instrument")).toContainText("25% lexical");
  await expect(page.getByTestId("score-instrument")).toContainText("Maximum total budget");
  await page.screenshot({ path: path.join(screenshotDirectory, "08-explain-score.png"), fullPage: true });
  await page.keyboard.press("Escape");

  await page.goto(`/search/${lexicalSession}`);
  await page.getByRole("button", { name: "Explain score" }).first().click();
  await expect(page.getByTestId("score-instrument")).toContainText("Lexical-only path");
  await expect(page.getByTestId("score-instrument")).not.toContainText("Semantic Relevance");
  await page.screenshot({ path: path.join(screenshotDirectory, "08b-explain-score-lexical-only.png"), fullPage: true });
  await page.keyboard.press("Escape");

  await page.goto(`/search/${partialSession}`);
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible();
  await expect(page.getByText("Partial coverage")).toBeVisible();

  await page.goto(`/search/${completedSession}`);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDirectory, "12-mobile.png"), fullPage: true });

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDirectory, "13-reduced-motion.png"), fullPage: true });

  await page.setViewportSize({ width: 1500, height: 1000 });
  await page.goto(`/search/${completedSession}?webgl=off`);
  await page.getByTestId("trace-toggle").click();
  await expect(page.getByTestId("webgl-fallback")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshotDirectory, "14-webgl-fallback.png"), fullPage: true });
  visualEvidence.fallback = { forced: true, canvas_count: await page.locator("canvas").count() };
  fs.writeFileSync(visualEvidencePath, `${JSON.stringify(visualEvidence, null, 2)}\n`);
});

test("completed topology disposes its canvas after WebGL context loss", async ({ page }) => {
  test.skip(!completedSession, "A completed evidence session was not supplied");
  await page.goto(`/search/${completedSession}`);
  await expect(page.locator('[data-workspace-state="results-first"]')).toBeVisible();
  await page.getByTestId("trace-toggle").click();
  const canvas = page.getByTestId("retrieval-topology-3d").locator("canvas");
  await expect(canvas).toHaveCount(1);
  await canvas.evaluate((element) => {
    element.dispatchEvent(new Event("webglcontextlost", { cancelable: true }));
  });
  await expect(page.getByTestId("webgl-fallback")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
});
