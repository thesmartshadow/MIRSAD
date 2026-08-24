# MIRSAD UI Precision Layout Fix

## Files changed

- `apps/web/src/pages/clusters-page.tsx`: added data-driven cluster-node sizing and deterministic collision-aware placement; expanded the SVG's vertical plotting bounds and aligned member counts with SVG font metrics.
- `apps/web/src/index.css`: added the responsive History ledger layout used below 900 px so query, status, time, metrics, and action retain separate grid areas.
- `apps/web/e2e/ui-layout-precision-live.spec.ts`: added a localhost-only, opt-in geometry and screenshot audit for all required routes, viewports, locales, SVG bounds, and document overflow.
- `reports/ui-layout-fix-screenshots/`: 84 rendered screenshots covering seven routes, six viewport sizes, and English/Arabic directionality.

## Defects fixed

- The real Baghdad cluster field had 8–9 node/orbit collisions depending on viewport. Nodes now retain time, relevance, and platform as preferred coordinates, then move only when their measured visual extents would intersect.
- Cluster node diameter now includes the member-count text requirement; count labels use centered anchoring and `dominant-baseline` rather than a fixed vertical offset.
- Cluster nodes, ticks, score rings, guides, and axis labels remain inside the SVG viewBox. Mobile retains a controlled internal map scroller instead of shrinking the evidence field into unreadability.
- The History ledger overflowed the page by 48 px at 768 px and allowed status/result columns to collide. Its compact layout now stacks time and metrics in explicit grid areas with no field loss.
- Mobile navigation is fully settled before visual measurement, preventing transient Sheet geometry from contaminating route screenshots.

## Breakpoints tested

`1920x1080`, `1440x900`, `1366x768`, `1024x768`, `768x1024`, and `390x844`, each in English LTR and Arabic RTL, across Search, Sources, Clusters, Analytics, Compare, History, and System.

The 84-view live audit passed with zero node collisions, clipped SVG content, unintended page overflow, RTL collisions, or console errors. Frontend validation also passed: 36 unit tests, Oxlint, TypeScript, production build, and isolated Playwright (11 passed, 9 intentional live-test skips).

## Known limitation

On narrow screens, the cluster and source maps intentionally scroll inside their own visualization regions to preserve readable geometry. The document itself does not overflow, and the accessible cluster/source records remain available below or beside the map.
