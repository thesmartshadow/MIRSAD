# MIRSAD v1.2 UI Correction

Date: 2026-08-24

## Scope

Frontend presentation and interaction only. This pass did not change backend behavior, API contracts, search, ranking, semantic scoring, clustering algorithms, routing, connectors, coverage, database semantics, or the application version.

## Global shell

- Replaced the two-tier header/navigation arrangement with one 64px shell contract driven by shared variables for header height, content offset, page gutter, page width, and section spacing.
- Removed page-specific header compensation, decorative page-header axes, the global technical grid, numbered navigation prefixes, and the decorative footer telemetry strip.
- Reorganized navigation around five primary destinations and a grouped workspace menu for Discover, Analyze, Library, and Operations.
- Implemented the navigation menu as a real accessible control: open, toggle close, Escape close, outside-click close, focus handling, and accurate `aria-expanded` state.
- Replaced `LOCAL` with the localized `ON-DEVICE` runtime indicator and the description “MIRSAD is running on this device.”

## Route corrections

- **Search:** tightened the command instrument, removed decorative field noise, made the idle retrieval diagram legible, and replaced fixed active-search columns with a bounded `minmax()` workspace. Active desktop retains parameter and trace rails; terminal results remain wide.
- **Clusters:** replaced decorative rings, ticks, arbitrary platform offsets, and unlabeled relationship curves with an explicit evidence map: X is first observed time, Y is aggregate relevance, and node size is member count. A bounded keyboard-aware inspector replaces floating tooltips.
- **Sources:** made the capability topology primary, recalculated source positions into collision-safe category rows and columns, and converted the oversized dark inspector into a compact readable technical inspector. Narrow layouts retain controlled map scrolling rather than shrinking labels into illegibility.
- **History:** created one authoritative row grid with independent query direction, a separate source column, exact metrics alignment, and a stacked mobile grid that prevents source/metric overlap.
- **Bookmarks:** joined record identity, analyst note, and actions into one proportional working row; notes use a compact default height and mobile records stack coherently.
- **Settings:** constrained content to a readable form measure, kept controls near labels, and made the mobile category strip own its horizontal overflow. The prior 150px page overflow at 430px and 390px is eliminated.
- **Analytics/System:** reduced equal-weight oversized telemetry surfaces and normalized section density and typography.
- **Compare:** added a truthful bounded empty state beneath the comparison controls.

## RTL and responsive validation

Validated English LTR and Arabic RTL at:

`1920x1080`, `1600x900`, `1440x900`, `1366x768`, `1280x800`, `1024x768`, `768x1024`, `430x932`, and `390x844`.

The 180-image evidence matrix is stored in `reports/mirsad-v1.2-ui-correction-screenshots/`. Automated bounding-box checks found no page-header clipping, page-wide horizontal overflow, or primary content outside the viewport. The focused SVG audit also found no source-label/node collisions, cluster-node collisions, or visualization content outside its owned bounds.

## Interaction validation

Validated real clicks and keyboard behavior for grouped navigation, mobile navigation, search controls, result explanation, diagnostics, bookmarks, History session opening, Settings tabs/actions, language switching, theme switching, dialogs, Sheets, Dropdowns, and route transitions. Browser console and unhandled page errors remained empty.

## Verification

- Frontend unit tests: 36 passed.
- TypeScript: passed.
- Oxlint: passed.
- Production Vite build: passed.
- Focused live collision matrix: passed, 72 route/locale/viewport captures.
- UI correction live matrix: passed, 180 captures.
- Isolated Playwright: 11 passed; 10 explicit live-only tests skipped by their guards.
- Accessibility serious/critical scan: passed.
- Browser stress observation: JS heap and DOM node counts did not grow monotonically.
- `git diff --check`: passed.

## Files changed

- `apps/web/src/components/layout/app-layout.tsx`: shared shell, grouped navigation, working menu, runtime indicator.
- `apps/web/src/components/shared/page.tsx`: reliable page-header structure.
- `apps/web/src/components/search/query-field.tsx`: simplified meaningful idle retrieval diagram.
- `apps/web/src/pages/search-page.tsx`: responsive active workspace rails.
- `apps/web/src/pages/clusters-page.tsx`: explicit evidence-map geometry and inspector.
- `apps/web/src/pages/history-page.tsx`: authoritative mixed-direction row layout.
- `apps/web/src/pages/bookmarks-page.tsx`: connected working-record layout.
- `apps/web/src/pages/settings-page.tsx`: compact form architecture.
- `apps/web/src/pages/sources-page.tsx`: collision-safe topology and primary ordering.
- `apps/web/src/pages/compare-page.tsx`: bounded empty state.
- `apps/web/src/lib/i18n.tsx`: localized navigation, runtime, and visualization labels.
- `apps/web/src/index.css`: shared sizing contract, responsive geometry, typography, and route precision rules.
- `apps/web/src/test/workflows.test.tsx`: active workspace regression coverage.
- `apps/web/e2e/mirsad.spec.ts`: current navigation and exact-action interaction coverage.
- `apps/web/e2e/ui-correction-live.spec.ts`: nine-viewport bilingual shell, overflow, menu, and screenshot matrix.
- `apps/web/e2e/ui-layout-precision-live.spec.ts`: source/cluster SVG collision assertions.
- `apps/web/e2e/v12-final-ui-live.spec.ts`: grouped navigation compatibility.

## Remaining limitations

Source and cluster maps use contained horizontal scrolling below their readable minimum canvas width. This is intentional: primary page content never overflows, the selected source/cluster inspector remains visible, and labels are not reduced below a readable size. No unresolved layout or interaction defect was observed in the tested matrix.
