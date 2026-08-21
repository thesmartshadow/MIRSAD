# Acceptance And Operations

## Deterministic Acceptance Matrix

| Case | Scenario | Automated evidence |
| --- | --- | --- |
| A | English query with multiple successful connectors | Backend acceptance fixtures |
| B | Arabic query | Backend acceptance plus narrow-viewport Playwright RTL workflow |
| C | Exact phrase | Backend acceptance and browser search control |
| D | One connector fails | API/service failure-isolation tests |
| E | Multiple connectors fail | Backend acceptance fixtures |
| F | No connector returns results | Backend acceptance fixtures |
| G | Missing YouTube key | Backend and browser partial-warning workflow |
| H | Rate-limited connector | HTTP classification and acceptance fixtures |
| I | Duplicate-heavy records | Backend preserved-group test and performance benchmark |
| J | Historical reopen | API and Playwright |
| K | Saved search create/rerun | API and Playwright |
| L | Bookmark create/note | API and Playwright |
| M | CSV export | API BOM/provenance/formula tests and Playwright download |
| N | JSON export | API schema/version test |
| O | Arabic RTL navigation | Playwright at 390 x 844 |
| P | Dark theme | Playwright |
| Q | Light theme | Automated accessibility route starts in light mode |
| R | Database reset | Confirmed API data action and CLI final verification |
| S | FTS rebuild | API action plus insert/update/delete synchronization tests |
| T | Frontend production build | `npm run build` |
| U | Social preset selects only configured supported connectors | Frontend capability-metadata fixture |
| V | Restricted social sources remain visible and disabled | Frontend source selector and metadata API fixtures |
| W | Social adapter normalization, missing metrics, Arabic, pagination, auth/rate/timeout behavior | Deterministic backend social connector suite |
| X | Platform diversity, Social Reach, and social analytics persistence | Backend end-to-end social fixture |

The Playwright suite also covers score explanation, diagnostics, sorting, analytics navigation, cluster opening, print report, Settings > Data confirmation, stale-search response ownership, state-preserving locale changes with loaded results, full route crawls in both languages at desktop and narrow widths, and automated serious/critical axe scans on Search, Sources, and Settings.

## Reproducible Commands

```bash
npm test
npm run test:e2e
npm run lint
npm run typecheck
npm run build
npm run evaluate:search
npm run evaluate:holdout
npm run benchmark
npm run benchmark:evidence
npm run doctor
npm run verify-sources
```

Install Chromium once with `npm --prefix apps/web exec playwright install chromium`. Backend and frontend suites do not require public network access.

## Performance Method

`npm run benchmark` performs one warmup and 12 recorded searches against three concurrent deterministic connectors, each delayed 50 ms. Every search collects 15 duplicate-heavy records and executes the production persistence, FTS, deduplication, ranking, clustering, analytics, and diagnostics pipeline in a temporary SQLite database. Median, p95, and median phase timings are written to `reports/performance.json` and `.md`.

This benchmark validates concurrency and identifies phase regressions; it is not a promise about third-party network latency.

`npm run benchmark:evidence` separately instruments the GDELT retry loop with a monotonic total budget, a fast/medium/slow mixed connector search, and bounded repeated-search memory snapshots. It states explicitly that the current REST response is non-streaming and that resource snapshots are observational rather than a formal leak proof.

## Live Verification

`npm run verify-sources` performs the least expensive implemented validation request for configured credentials and access. Optional unconfigured/restricted/network failures remain explicit but do not make the command exit non-zero; internal registry/verifier failures do. `npm run verify:live` is intentionally separate. It runs actual harmless queries through connector normalization, records stage/status/latency/error telemetry, and never changes a failed source into a fixture success. Review the timestamp and environment in `reports/live-connectors.*` before using it as demonstration evidence.

## Startup QA

`npm run doctor` must have no FAIL lines. `.env` may be WARN because safe defaults operate without credentials. `./start.sh` uses strict ports and does not report success until both the API health endpoint and frontend respond on 8000/5173. Open `http://127.0.0.1:5173`, inspect `.run/api.log` and `.run/web.log`, then stop with `./stop.sh`.
