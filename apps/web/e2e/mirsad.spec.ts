import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  browserErrors.set(page, errors);
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
});

test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page) ?? []).toEqual([]);
});

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter(
      ({ impact }) => impact === "critical" || impact === "serious",
    ),
  ).toEqual([]);
}

async function navigateThroughUi(page: Page, path: string) {
  const visibleLink = page.locator(`a[href="${path}"]:visible`).first();
  if (await visibleLink.isVisible().catch(() => false)) {
    await visibleLink.click();
    return;
  }
  await page.locator('[data-navigation-menu="trigger"]:visible').click();
  await page
    .locator(`[data-navigation-menu="content"] a[href="${path}"]`)
    .click();
}

test.beforeAll(async ({ request }) => {
  if (
    process.env.MIRSAD_LIVE_BASE_URL ||
    process.env.MIRSAD_LIVE_SESSION_ID ||
    process.env.MIRSAD_FUNCTIONAL_SESSION_ID
  )
    return;
  const databaseUrl =
    process.env.MIRSAD_E2E_DATABASE_URL ?? "sqlite:///../../data/e2e.db";
  if (!/(?:test|e2e)[^/]*\.db$/i.test(databaseUrl))
    throw new Error("Destructive E2E setup requires an isolated test database");
  const response = await request.post("/api/v1/data/actions/reset_database", {
    data: { confirm: true },
  });
  expect(response.ok()).toBeTruthy();
  const sourcesResponse = await request.get("/api/v1/sources");
  expect(sourcesResponse.ok()).toBeTruthy();
  const sources = (await sourcesResponse.json()) as { key: string }[];
  for (const source of sources) {
    if (source.key === "mock") continue;
    const disabled = await request.patch(`/api/v1/sources/${source.key}`, {
      data: { enabled: false },
    });
    expect(disabled.ok()).toBeTruthy();
  }
});

test("opt-in live persisted session renders, explains, and exports", async ({
  page,
  request,
}) => {
  const sessionId = process.env.MIRSAD_LIVE_SESSION_ID;
  test.skip(!sessionId, "Live pilot session not supplied");
  let newSearchRequests = 0;
  page.on("request", (outbound) => {
    if (
      outbound.method() === "POST" &&
      new URL(outbound.url()).pathname === "/api/v1/searches"
    )
      newSearchRequests += 1;
  });
  await page.goto(`/search/${sessionId}`);
  await expect(page.getByText("Results", { exact: true })).toBeVisible();
  await expect(
    page.getByText("open data", { exact: true }).first(),
  ).toBeVisible();
  expect(await page.locator('a[target="_blank"]').count()).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Explain score" }).first().click();
  await expect(
    page.getByText("Deterministic signals used for this ranking"),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Search diagnostics" }).click();
  await expect(page.getByRole("cell", { name: "gdelt" })).toBeVisible();
  await page.keyboard.press("Escape");

  const jsonExport = await request.get(
    `/api/v1/searches/${sessionId}/export?format=json`,
  );
  expect(jsonExport.ok()).toBeTruthy();
  expect((await jsonExport.json()).records.length).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(
    page.getByText("open data", { exact: true }).first(),
  ).toHaveAttribute("dir", "auto");

  await page.getByRole("button", { name: "تغيير اللغة" }).click();
  await page.getByText("الإنجليزية", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page).toHaveURL(new RegExp(`/search/${sessionId}$`));
  await expect(
    page.getByText("open data", { exact: true }).first(),
  ).toBeVisible();
  expect(newSearchRequests).toBe(0);
});

test("opt-in live Arabic session preserves retrieved content across direction changes", async ({
  page,
}) => {
  const sessionId = process.env.MIRSAD_LIVE_ARABIC_SESSION_ID;
  test.skip(!sessionId, "Live Arabic pilot session not supplied");
  let newSearchRequests = 0;
  page.on("request", (outbound) => {
    if (
      outbound.method() === "POST" &&
      new URL(outbound.url()).pathname === "/api/v1/searches"
    )
      newSearchRequests += 1;
  });

  await page.goto(`/search/${sessionId}`);
  const liveArabicText = page.getByText(/اسمي عبدالله من العراق/).first();
  await expect(liveArabicText).toBeVisible();
  await expect(liveArabicText).toHaveAttribute("dir", "auto");
  expect(await page.locator('a[target="_blank"]').count()).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(liveArabicText).toBeVisible();
  await expect(liveArabicText).toHaveAttribute("dir", "auto");

  await page.getByRole("button", { name: "تغيير اللغة" }).click();
  await page.getByText("الإنجليزية", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page).toHaveURL(new RegExp(`/search/${sessionId}$`));
  await expect(liveArabicText).toBeVisible();
  expect(newSearchRequests).toBe(0);
});

test("opt-in functional production state is consistent across major routes", async ({
  page,
}) => {
  const sessionId = process.env.MIRSAD_FUNCTIONAL_SESSION_ID;
  test.skip(!sessionId, "Functional production session not supplied");

  await page.goto(`/search/${sessionId}`);
  await expect(page.getByText("Results", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Explain score" }).first().click();
  await expect(
    page.getByText("Deterministic signals used for this ranking"),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  const bookmarkButton = page
    .getByRole("button", { name: /Bookmark result|Bookmarked/ })
    .first();
  if ((await bookmarkButton.getAttribute("aria-label")) === "Bookmark result")
    await bookmarkButton.click();

  await navigateThroughUi(page, "/history");
  await expect(page.getByText("بغداد", { exact: true }).first()).toBeVisible();

  await navigateThroughUi(page, "/analytics");
  await expect(page.getByText("Content records", { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Analytics scope" }).click();
  await page.getByRole("option", { name: "Current search session" }).click();
  await expect(page.getByText(/Analytics for:/)).toBeVisible();

  await navigateThroughUi(page, "/clusters");
  await expect(page.getByRole("heading", { name: "Story clusters" })).toBeVisible();
  await navigateThroughUi(page, "/compare");
  await expect(page.getByRole("heading", { name: "Compare searches" })).toBeVisible();
  await navigateThroughUi(page, "/saved");
  await expect(
    page.getByRole("heading", { name: "Saved searches", level: 2, exact: true }),
  ).toBeVisible();
  await navigateThroughUi(page, "/bookmarks");
  await expect(
    page.getByRole("heading", { name: "Bookmarks", level: 2, exact: true }),
  ).toBeVisible();
  await navigateThroughUi(page, "/sources");
  await expect(page.getByText("Bluesky", { exact: true })).toBeVisible();
  await expect(page.getByText("Web discovery disabled").first()).toBeVisible();
  await navigateThroughUi(page, "/system");
  await expect(page.getByText(/1\.1\.0/).first()).toBeVisible();
  await navigateThroughUi(page, "/settings");
  await expect(page.getByRole("heading", { name: "Settings", level: 2 })).toBeVisible();

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByRole("button", { name: "تغيير اللغة" }).click();
  await page.getByText("الإنجليزية", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
});

test("search, explanation, diagnostics, export, history, saved search and bookmark", async ({
  page,
}) => {
  await page.goto("/search");
  await expect(page.getByLabel("Keyword or phrase")).toBeVisible();
  await page.getByText("Sources and advanced options", { exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "YouTube" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await expect(
    page.getByText("Requires a YouTube Data API key."),
  ).toBeVisible();
  await expect(page.getByLabel("Search mode")).toContainText("Balanced");
  await page.getByLabel("Search mode").click();
  await page.getByRole("option", { name: "Deep" }).click();
  await expect(page.getByText("Wider multi-round discovery")).toBeVisible();
  await page.getByLabel("Search mode").click();
  await page.getByRole("option", { name: "Balanced" }).click();
  await page.getByLabel("Keyword or phrase").fill("public policy");
  await page.getByText("Best Match", { exact: true }).click();
  await page.getByRole("option", { name: "Newest" }).click();
  await page.getByText("Exact phrase", { exact: true }).click();
  await page.getByRole("button", { name: "Run search" }).click();

  await expect(page.getByText("public policy public briefing 1")).toBeVisible();

  await page.getByRole("button", { name: "Explain score" }).first().click();
  await expect(
    page.getByText("Deterministic signals used for this ranking"),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Search diagnostics" }).click();
  await expect(page.getByText("Phase timings")).toBeVisible();
  await expect(
    page
      .getByRole("table", { name: "Source funnel" })
      .getByRole("cell", { name: "mock" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export" }).click();
  await page.getByText("CSV", { exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/mirsad-.*\.csv/);

  await page.getByRole("button", { name: "Bookmark result" }).first().click();
  await expect(
    page.getByRole("button", { name: "Bookmarked" }).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "Save search" }).click();
  await page.getByLabel("Saved search name").fill("Policy daily review");
  await page.getByRole("button", { name: "Save changes" }).click();

  await navigateThroughUi(page, "/analytics");
  await expect(
    page.getByText("Mentions over time", { exact: true }),
  ).toBeVisible();
  await navigateThroughUi(page, "/clusters");
  await page.locator(".cluster-index button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText(/First Seen by MIRSAD/i),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  await navigateThroughUi(page, "/history");
  await expect(page.getByText("public policy").first()).toBeVisible();
  await page.getByRole("button", { name: "Open", exact: true }).first().click();
  await expect(page.getByText("Results")).toBeVisible();

  await navigateThroughUi(page, "/saved");
  await expect(page.getByText("Policy daily review")).toBeVisible();
  await page.getByRole("button", { name: "Run again" }).click();
  await expect(page.getByText("public policy public briefing 1")).toBeVisible();

  await navigateThroughUi(page, "/bookmarks");
  await expect(page.getByText("public policy public briefing 1")).toBeVisible();
  await page.getByLabel("Local note").fill("Include in briefing");
  await page.getByRole("button", { name: "Save changes" }).click();
});

test("Arabic RTL and theme controls work at a narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/search");
  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await page.locator('[data-navigation-menu="trigger"]:visible').click();
  const mobileSidebar = page.locator(
    '[data-slot="sidebar"][data-mobile="true"]',
  );
  await expect(mobileSidebar).toBeVisible();
  await expect(mobileSidebar).toHaveAttribute("data-side", "right");
  await expect(mobileSidebar).toHaveAttribute("dir", "rtl");
  await page.keyboard.press("Escape");
  await expect(mobileSidebar).not.toBeVisible();

  await page.getByRole("button", { name: "تبديل السمة" }).click();
  await page.getByText("داكن", { exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);

  await page.getByLabel("كلمة مفتاحية أو عبارة").fill("وزارة الصحة");
  await page.getByRole("button", { name: "تشغيل البحث" }).click();
  await expect(
    page.getByText(/وزارة الصحة public briefing/i).first(),
  ).toBeVisible();
  await expect(page.locator("main")).toBeVisible();
});

test("locale switching is immediate and preserves form and navigation state", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.setItem("mirsad.locale", "ar"));
  await page.goto("/search");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByLabel("كلمة مفتاحية أو عبارة").fill("وزارة الصحة Microsoft");
  await page.locator('[data-navigation-menu="trigger"]:visible').click();
  await expect(page.locator('[data-slot="sidebar"][data-mobile="true"]')).toHaveAttribute("data-side", "right");
  await page.keyboard.press("Escape");

  for (let index = 0; index < 20; index += 1) {
    const currentlyArabic = index % 2 === 0;
    await page
      .getByRole("button", {
        name: currentlyArabic ? "تغيير اللغة" : "Change language",
      })
      .click();
    await page
      .getByText(currentlyArabic ? "الإنجليزية" : "Arabic", { exact: true })
      .click();
    await expect(page.locator("html")).toHaveAttribute(
      "dir",
      currentlyArabic ? "ltr" : "rtl",
    );
  }

  await expect(page.getByLabel("كلمة مفتاحية أو عبارة")).toHaveValue(
    "وزارة الصحة Microsoft",
  );
  await page.locator('[data-navigation-menu="trigger"]:visible').click();
  await expect(page.locator('[data-slot="sidebar"][data-mobile="true"]')).toHaveAttribute("data-side", "right");
  await page.keyboard.press("Escape");
});

test("a completed stale search cannot redirect after route navigation", async ({
  page,
}) => {
  await page.route("**/api/v1/searches", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.continue().catch(() => undefined);
  });

  await page.goto("/search");
  await page.getByLabel("Keyword or phrase").fill("slow stale request");
  await page.getByRole("button", { name: "Run search" }).click();
  await navigateThroughUi(page, "/settings");
  await expect(page).toHaveURL(/\/settings$/);
  await page.waitForTimeout(900);
  await expect(page).toHaveURL(/\/settings$/);
});

test("language switching preserves a loaded session and search controls", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/v1/searches", {
    data: {
      query: "وزارة الصحة Microsoft",
      sources: ["mock"],
      time_range: "30d",
      language: "all",
      limit: 25,
      exact_phrase: false,
      sort: "best_match",
    },
  });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session.id as string;
  let pageSearchRequests = 0;
  page.on("request", (outbound) => {
    if (
      outbound.method() === "POST" &&
      new URL(outbound.url()).pathname === "/api/v1/searches"
    )
      pageSearchRequests += 1;
  });

  await page.goto(`/search/${sessionId}`);
  await expect(page.getByText(/public briefing 1/i).first()).toBeVisible();
  await page.getByText("Sources and advanced options", { exact: true }).click();
  await page.getByLabel("Sort mode").click();
  await page.getByRole("option", { name: "Newest" }).click();
  await page.getByRole("checkbox", { name: "Exact phrase" }).click();

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page).toHaveURL(new RegExp(`/search/${sessionId}$`));
  await expect(page.getByLabel("كلمة مفتاحية أو عبارة")).toHaveValue(
    "وزارة الصحة Microsoft",
  );
  await expect(page.getByLabel("ترتيب النتائج")).toContainText("الأحدث");
  await expect(
    page.getByRole("checkbox", { name: "عبارة مطابقة" }),
  ).toBeChecked();
  await expect(page.getByText(/public briefing 1/i).first()).toBeVisible();

  await page.getByRole("button", { name: "تغيير اللغة" }).click();
  await page.getByText("الإنجليزية", { exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByLabel("Keyword or phrase")).toHaveValue(
    "وزارة الصحة Microsoft",
  );
  expect(pageSearchRequests).toBe(0);
});

test("all major routes render in English and Arabic at desktop and narrow widths", async ({
  page,
}) => {
  const routes = [
    "/search",
    "/analytics",
    "/clusters",
    "/compare",
    "/history",
    "/saved",
    "/bookmarks",
    "/sources",
    "/system",
    "/settings",
  ];

  for (const path of routes) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  }

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of routes) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  }
});

test("twenty locale switches remain stable across major analytical routes", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/v1/searches", {
    data: {
      query: "locale stress evidence",
      sources: ["mock"],
      time_range: "7d",
      language: "all",
      limit: 25,
      exact_phrase: false,
      sort: "best_match",
    },
  });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session.id as string;
  const routes = ["/search", `/search/${sessionId}`, "/analytics", "/settings"];

  for (const path of routes) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    for (let index = 0; index < 5; index += 1) {
      const isArabic =
        (await page.locator("html").getAttribute("lang")) === "ar";
      await page
        .getByRole("button", {
          name: isArabic ? "تغيير اللغة" : "Change language",
        })
        .click();
      await page
        .getByText(isArabic ? "الإنجليزية" : "Arabic", { exact: true })
        .click();
      await expect(page.locator("html")).toHaveAttribute(
        "dir",
        isArabic ? "ltr" : "rtl",
      );
      await expect(page).toHaveURL(new RegExp(`${path.replace("/", "\\/")}$`));
    }
  }
});

test("print report and settings data controls render from stored data", async ({
  page,
  request,
}) => {
  const search = await request.post("/api/v1/searches", {
    data: {
      query: "institutional report",
      sources: ["mock"],
      time_range: "7d",
      language: "all",
      limit: 5,
      exact_phrase: false,
      sort: "best_match",
    },
  });
  expect(search.ok()).toBeTruthy();
  await page.goto("/history");
  await page.getByRole("button", { name: "Open", exact: true }).first().click();
  await page.getByRole("button", { name: "Print report" }).click();
  await expect(page.locator(".print-report")).toBeVisible();
  await expect(page.getByText("Platform distribution")).toBeVisible();

  await navigateThroughUi(page, "/settings");
  await page.getByRole("tab", { name: "Data" }).click();
  await expect(page.getByText("Local record counts")).toBeVisible();
  await page.getByRole("button", { name: "Rebuild FTS index" }).click();
  await expect(page.getByText(/cannot be undone/i)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
});

test("key analytical pages have no serious automated accessibility findings", async ({
  page,
}) => {
  await page.goto("/search");
  await expect(page.getByLabel("Keyword or phrase")).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.goto("/settings");
  await expect(
    page.getByRole("heading", { name: "Settings", level: 2 }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByText("Arabic", { exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/search", "/sources", "/settings"]) {
    await page.goto(path);
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.locator("main")).toBeVisible();
    await expectNoSeriousAccessibilityViolations(page);
  }
});

test("all production portal primitives preserve direction, focus, and keyboard behavior", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/v1/searches", {
    data: {
      query: "portal direction evidence",
      sources: ["mock", "youtube"],
      time_range: "7d",
      language: "all",
      limit: 10,
      exact_phrase: false,
      sort: "best_match",
    },
  });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session.id as string;
  await page.goto(`/search/${sessionId}`);
  await expect(page.getByText(/public briefing 1/i)).toBeVisible();
  await page.getByText("Sources and advanced options", { exact: true }).click();

  const expectPortalDirection = async (
    selector: string,
    direction: "ltr" | "rtl",
  ) => {
    const portal = page.locator(selector).last();
    await expect(portal).toBeVisible();
    await portal.evaluate(async (element) => {
      await Promise.all(
        element
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished.catch(() => undefined)),
      );
    });
    expect(
      await portal.evaluate((element) => getComputedStyle(element).direction),
    ).toBe(direction);
    const box = await portal.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(-1);
    expect(box!.x + box!.width).toBeLessThanOrEqual(
      (await page.viewportSize())!.width + 1,
    );
    return portal;
  };

  for (const locale of ["en", "ar", "en"] as const) {
    const direction = locale === "ar" ? "rtl" : "ltr";
    await expect(page.locator("html")).toHaveAttribute("dir", direction);

    const exportTrigger = page.getByRole("button", {
      name: locale === "ar" ? "تصدير" : "Export",
    });
    await exportTrigger.focus();
    await page.keyboard.press("Enter");
    await expectPortalDirection(
      '[data-slot="dropdown-menu-content"]',
      direction,
    );
    await page.keyboard.press("ArrowDown");
    await expect(page.locator('[role="menuitem"]:focus')).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(exportTrigger).toBeFocused();

    const sortTrigger = page.getByLabel(
      locale === "ar" ? "ترتيب النتائج" : "Sort mode",
    );
    await sortTrigger.focus();
    await page.keyboard.press("Enter");
    await expectPortalDirection('[data-slot="select-content"]', direction);
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Escape");
    await expect(sortTrigger).toBeFocused();

    const tooltipTrigger = page.getByRole("button", {
      name: locale === "ar" ? "YouTube القدرات" : "YouTube capabilities",
    });
    await tooltipTrigger.focus();
    await expectPortalDirection('[data-slot="tooltip-content"]', direction);
    await page.keyboard.press("Escape");

    const sheetTrigger = page
      .getByRole("button", {
        name: locale === "ar" ? "شرح الدرجة" : "Explain score",
      })
      .first();
    await sheetTrigger.focus();
    await page.keyboard.press("Enter");
    const sheet = await expectPortalDirection(
      '[data-slot="sheet-content"]',
      direction,
    );
    await expect(sheet).toHaveAttribute(
      "data-side",
      locale === "ar" ? "left" : "right",
    );
    expect(
      await sheet.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(sheetTrigger).toBeFocused();

    const dialogTrigger = page.getByRole("button", {
      name: locale === "ar" ? "تشخيص البحث" : "Search diagnostics",
    });
    await dialogTrigger.focus();
    await page.keyboard.press("Enter");
    const dialog = await expectPortalDirection(
      '[data-slot="dialog-content"]',
      direction,
    );
    expect(
      await dialog.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialogTrigger).toBeFocused();

    if (locale === "en") {
      await expect(
        page
          .getByText("Requires a YouTube Data API key.", { exact: true })
          .first(),
      ).toBeVisible();
      await page.getByRole("button", { name: "Change language" }).click();
      await page.getByText("Arabic", { exact: true }).click();
    } else {
      await expect(
        page
          .getByText("يتطلب مفتاح واجهة بيانات YouTube.", { exact: true })
          .first(),
      ).toBeVisible();
      await page.getByRole("button", { name: "تغيير اللغة" }).click();
      await page.getByText("الإنجليزية", { exact: true }).click();
    }
  }
  await page.goto("/sources");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(
    page.getByText("يتطلب مفتاح واجهة بيانات YouTube."),
  ).toBeVisible();
  await expect(
    page.getByText("API key not configured", { exact: true }),
  ).toHaveCount(0);
});

test("bounded browser stress has no obvious monotonic resource growth", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/v1/searches", {
    data: {
      query: "browser memory evidence",
      sources: ["mock"],
      time_range: "7d",
      language: "all",
      limit: 10,
      exact_phrase: false,
      sort: "best_match",
    },
  });
  const sessionId = (await created.json()).session.id as string;
  await page.goto(`/search/${sessionId}`);
  await expect(page.getByText(/public briefing 1/i)).toBeVisible();
  const client = await page.context().newCDPSession(page);
  await client.send("Performance.enable");

  const snapshot = async () => {
    await client.send("HeapProfiler.collectGarbage");
    const metrics = await client.send("Performance.getMetrics");
    const values = Object.fromEntries(
      metrics.metrics.map((metric) => [metric.name, metric.value]),
    );
    return {
      js_heap_bytes: values.JSHeapUsedSize ?? 0,
      nodes: values.Nodes ?? 0,
      documents: values.Documents ?? 0,
    };
  };

  const before = await snapshot();
  for (let index = 0; index < 20; index += 1) {
    const arabic = (await page.locator("html").getAttribute("lang")) === "ar";
    await page
      .getByRole("button", {
        name: arabic ? "تغيير اللغة" : "Change language",
      })
      .click();
    await page
      .getByText(arabic ? "الإنجليزية" : "Arabic", { exact: true })
      .click();
  }
  for (let index = 0; index < 8; index += 1) {
    const sheetTrigger = page
      .getByRole("button", { name: "Explain score" })
      .first();
    await sheetTrigger.click();
    await expect(page.locator('[data-slot="sheet-content"]')).toBeVisible();
    await page.keyboard.press("Escape");
    const dialogTrigger = page.getByRole("button", {
      name: "Search diagnostics",
    });
    await dialogTrigger.click();
    await expect(page.locator('[data-slot="dialog-content"]')).toBeVisible();
    await page.keyboard.press("Escape");
  }
  for (const path of [
    "/analytics",
    "/clusters",
    "/history",
    `/search/${sessionId}`,
  ]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
  }
  const after = await snapshot();
  console.log(
    `BROWSER_MEMORY_OBSERVATION ${JSON.stringify({ before, after })}`,
  );
  expect(after.js_heap_bytes - before.js_heap_bytes).toBeLessThan(
    32 * 1024 * 1024,
  );
  expect(after.nodes - before.nodes).toBeLessThan(10_000);
  expect(after.documents - before.documents).toBeLessThan(20);
});
