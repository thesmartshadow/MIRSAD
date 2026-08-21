# MIRSAD v1.1 Search Evolution

## Executive assessment

MIRSAD 1.1.0 evolves the existing deterministic MAFER Phase 2 search into a real-time analyst workspace without changing the production ranker, clustering algorithm, source quotas, or Phase 3 promotion state. Search jobs now expose bounded server-sent progress, the browser renders acquisition progress before final ranking, and the final list is published only after the authoritative ranking and clustering stages finish.

The live eight-query matrix used real configured connectors and the operator database without reset. It demonstrated immediate feedback, stable final results, partial-failure isolation, literal hashtag and identifier handling, Arabic/English/RTL presentation, and truthful zero-result behavior. One internal defect was found: identifier matching admitted unrelated CVEs sharing the year token. The retrieval-stage matcher now requires the literal punctuation-preserving identifier. The frozen ranking formula was not touched.

## Baseline

The controlled baseline used an isolated temporary database and deterministic connectors. Cold semantic work was 1,392.34 ms; a repeat query was 20.43 ms with 20/20 content-embedding cache hits; a different query over the same content was 23.20 ms with 20/20 hits. The previous live Baghdad trace was approximately 5,632 ms total, dominated by 4,324 ms of external collection and 904 ms of semantic work.

Machine-readable evidence: [search-evolution-baseline.json](search-evolution-baseline.json) and [search-evolution-performance.json](search-evolution-performance.json).

## Architecture changes

The synchronous `POST /api/v1/search` route remains compatible. `POST /api/v1/search/jobs` creates a job and reserved session identifier, while `GET /api/v1/search/jobs/{job_id}/events` streams progress. Each job runs the existing `SearchService` with an event sink and an independent SQLAlchemy session. No new database, queue, hosted service, or ranking path was introduced.

The registry is bounded to 32 jobs, each event history to 128 events, and completed jobs expire after 900 seconds by default. Capacity returns HTTP 429. Opaque UUID job identifiers only address registry entries. Browser disconnect does not cancel or corrupt the search. Cancellation was not added because connector cancellation would require unsafe architectural changes; optional work remains bounded by the existing request, round, and connector time budgets.

## Real-time search architecture

The browser creates a job, installs an `EventSource`, and reduces typed events into a discriminated search state. The workspace becomes visible in the initiating interaction. A generation token, job identity checks, `AbortController`, and terminal-state guards prevent late Search A events or responses from overwriting Search B. History navigation remains independent from an active job.

The final session read model is fetched only after `search.completed` or `search.partial`. Streaming counters are diagnostic and never persisted as final result counts. The live matrix measured job creation from 0.87 to 6.65 ms and first events from 19.00 to 50.18 ms.

## SSE protocol

Implemented typed, sequenced events include `search.started`, planning start/completion, source selected/started/progress/completed/degraded/failed/skipped, collection progress, normalization/persistence completion, ranking start/completion, clustering start/completion, and terminal completed/partial/failed events. Payloads contain source names, safe categories, counts, timings, and acquisition modes. Tests verify ordering, partial and failed states, disconnect behavior, expiration, bounded history, and registry capacity. Credentials, exception dumps, and arbitrary resource references are not emitted.

## Search state machine

Whole-search states are `idle`, `creating`, `planning`, `collecting`, `normalizing`, `ranking`, `clustering`, `completed`, `partial`, `failed`, and `cancelled`. Per-source states are separate. Post-terminal non-terminal events and events for another job are ignored. Final ranking order is locked for the session; acquisition views never masquerade as ranked output.

## New search workspace

Desktop uses a responsive filter rail, dominant session workspace, and bounded live-trace rail. Medium and narrow layouts keep results central and expose controls and trace in shadcn Sheets. The command bar supports Enter, query clearing, and `/` or Ctrl/Cmd+K focus. Automatic routing is explicitly described and advanced controls use progressive disclosure. Session tabs provide Results, Clusters, Timeline, and Analysis without duplicating global analytics.

Source progress is conveyed by icon, text, and color. Partial searches retain valid results and name the failed provider rather than displaying a full-page failure. Loading preserves the layout with skeletons. Comfortable and Compact density are local UI preferences only.

## Result-card redesign

Cards now present source, author, timestamp, title, relevant text, canonical domain, acquisition mode, language, cluster, compact relevance, bookmark/open actions, and an Explain Score dialog. The explanation separates lexical, semantic, secondary-quality, and penalty components and states that relevance is not factual correctness.

## Snippet and highlighting implementation

The API returns a plain snippet, matched terms, structured highlight ranges, and a semantic-only flag. Highlighting is rendered from React text nodes and `<mark>` elements. Retrieved HTML is never executed and `dangerouslySetInnerHTML` is not used for result content. Semantic-only candidates receive a label rather than invented lexical highlighting. Malicious markup regression tests render it as text.

## Semantic profiling

Instrumentation separates model load, query encoding, cache lookup, uncached candidate encoding, similarity, cache hits/misses, and batch size. After instrumentation, a controlled cold run measured 1,224.92 ms semantic time: 767.27 ms model load, 19.07 ms query encoding, 436.55 ms candidate generation, and 1.78 ms similarity. Warm repeat was 20.82 ms with 20 hits and no candidate generation. Warm new-query time was 23.27 ms with the same content cache hits.

The 12.02% cold difference is ordinary model-start variance; the 1.91% warm difference is measurement noise and is not claimed as a compute improvement. Perceived speed improved because useful progress begins before external collection completes.

## Embedding cache decision

No persistent embedding table was added. Measurement showed the existing bounded in-process content cache already removes repeated warm candidate generation, and a new persistent vector representation did not clear the performance/complexity gate. Cache identity still includes content and model state. Exact cached-versus-uncached score and ordering equivalence is covered by regression tests.

## Batching decision

The existing bounded batch encoder was retained with maximum batch size 32. Tests assert the bound and verify cache hit, miss, model-version mismatch, and exact cached/uncached output equivalence. No unbounded query embedding cache was introduced.

## SQLite and FTS audit

Representative `EXPLAIN QUERY PLAN` output showed FTS5 virtual-table lookup for lexical candidates. Explicit BM25 ordering remains because changing to implicit rank would change production semantics. Session history and session-result reads now have planner-supported indexes on `search_sessions.started_at` and `(search_session_id, rank)`. Migrations are additive. Final integrity is `ok`, foreign-key violations are zero, and `content_items=785` equals `content_fts=785`.

## Intent retrieval lanes

Existing MAFER intent and lattice behavior remains authoritative. HANDLE and HASHTAG variants preserve `@` and `#`; IDENTIFIER and EXACT_PHRASE preserve punctuation; Arabic original text remains distinct from internal normalization; entity/person variants remain conservative; topic queries retain semantic retrieval. Connector request variants are recorded in the source funnel.

The live exact identifier `CVE-2026-61371` exposed a retrieval defect: generic lattice tokens admitted other `CVE-2026-*` records. Identifier-only local matching now requires the NFKC/casefold literal identifier in title, text, URL, handle, or tags. A targeted live rerun correctly returned zero rather than unrelated CVEs. No result was injected.

## Source-yield telemetry

Each source trace records acquisition mode, requests, variants, latency, fetched, matched, normalized, admitted, final top-k contribution, health state, and error category. The compact normal trace exposes searched/failed sources, candidates, duration, results, and stop reason; advanced diagnostics preserve the full requested-to-top-k funnel. These metrics describe retrieval utility, not trust or credibility.

## Shadow utility evaluation

The existing Phase 3 `source_utility_observations` and `shadow_evaluations` tables were reused. Production and shadow decisions remain separately versioned; shadow rows are marked non-user-visible and cannot alter connector selection or final ranking. The final database contains 136 shadow evaluations. No adaptive source utility, stopping policy, query-aware fusion, or alternative model was promoted.

## Performance before and after

| Controlled case | Baseline semantic | After semantic | Baseline wall | After wall | Cache |
|---|---:|---:|---:|---:|---|
| Cold | 1,392.34 ms | 1,224.92 ms | 1,519.00 ms | 1,356.92 ms | 0/20 hits |
| Warm repeat | 20.43 ms | 20.82 ms | 122.24 ms | 122.45 ms | 20/20 hits |
| Warm new query, cached content | 23.20 ms | 23.27 ms | 120.69 ms | 121.99 ms | 20/20 hits |

RSS was 694.21 MiB after the cold baseline and 696.74 MiB after the cold instrumented run. There is no material memory regression. The browser live test observed 27.4 MiB JS heap/4,516 nodes before its workflow and 24.7 MiB/2,694 nodes afterward. External connector time is reported independently and is not attributed to local optimization.

## Live matrix

The bounded matrix used automatic routing, Balanced mode, real public APIs, a 30-day scope except all-time exact CVE, and no SearXNG. It did not reset the operator database.

| Query | Status | Results | Job | First event | First source | Collection | Semantic | Total | Stop |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `بغداد` | completed | 30 | 6.65 ms | 38.60 ms | 427.67 ms | 955.76 ms | 27.97 ms | 1,157 ms | USER_LIMIT |
| `الذكاء الاصطناعي` | partial | 30 | 0.91 ms | 24.08 ms | 967.25 ms | 4,348.08 ms | 1,941.63 ms | 7,048 ms | USER_LIMIT |
| `وزارة التخطيط` | partial | 30 | 0.95 ms | 25.37 ms | 514.20 ms | 3,975.50 ms | 1,957.16 ms | 6,664 ms | USER_LIMIT |
| `#بغداد` | completed | 14 | 0.97 ms | 38.92 ms | 572.87 ms | 1,017.26 ms | 0.00 ms | 1,481 ms | SATISFIED |
| `Linux kernel security` | partial | 30 | 0.87 ms | 20.14 ms | 1,154.42 ms | 2,643.56 ms | 2,072.40 ms | 6,042 ms | USER_LIMIT |
| `OpenAI` | completed | 30 | 1.02 ms | 19.00 ms | 557.22 ms | 1,195.95 ms | 1,026.45 ms | 2,894 ms | USER_LIMIT |
| `@openai` | partial | 0 | 0.96 ms | 28.46 ms | 379.43 ms | 1,700.92 ms | 0.00 ms | 1,739 ms | LOW_MARGINAL_GAIN |
| `CVE-2026-61371` | partial | 0 | 5.06 ms | 50.18 ms | 456.13 ms | 3,812.31 ms | 0.00 ms | 3,848 ms | LOW_MARGINAL_GAIN |

The hashtag lane returned real YouTube and Mastodon matches. Zero handle results are an honest capability/coverage outcome: direct sources fetched records but did not match the literal handle, GitHub was temporarily externally limited, and web discovery was disabled. The CVE zero result is honest after the false-positive fix. Top-five manual sanity inspection found literal or clearly on-topic evidence for every non-empty query; this is qualitative smoke evidence, not a precision claim. Full per-event and per-source evidence is in [search-evolution-live-matrix.json](search-evolution-live-matrix.json).

## UI screenshots

Evidence is stored in [search-evolution-screenshots](search-evolution-screenshots/): `desktop-idle-search.png`, `desktop-active-live-search.png`, `desktop-completed-results.png`, `result-explain-score.png`, `partial-search.png`, `arabic-rtl.png`, and `mobile-narrow-search.png`.

## RTL validation

Playwright exercised Arabic and English at desktop and narrow widths. The application root controls direction. Source rails and panel order follow RTL while URLs, identifiers, handles, scores, numbers, and timestamps use bidi isolation where necessary. The live Arabic screenshot confirms the command bar, source trace, results, tabs, and controls remain aligned.

## Failure isolation

GDELT exceeded its 3-second interactive budget on three matrix cases; later requests encountered its open circuit without another network request. Valid results from healthy sources were retained as partial sessions. GitHub's temporary anonymous 403 is categorized `external_limit` and does not mutate long-term utility. Bluesky's public AppView returned external HTTP 403 during the final source probe; it remains configured but externally unavailable, not unconfigured. Later-page degradation tests preserve first-page records and permit recovery after success.

SearXNG remains intentionally disabled. X, Threads, and Reddit are reported `web_discovery_disabled`, not connector failures. No CAPTCHA bypass, proxy rotation, platform login, or scraping was attempted.

## Security

The full backend suite covers fixed-host SSRF boundaries, private addresses, redirects, URL classifiers, manual import, SQL parameterization, feedback validation, CSV formula escaping, and secret handling. SSE job IDs are opaque and registry-only, queues are bounded, event fields are allowlisted, and error messages are sanitized. Search snippets render as inert text. The production bundle scan found no configured secret. Streaming paths cannot select hosts, files, or fetch targets.

## Tests

- Backend: 211 passed.
- Frontend Vitest: 27 passed across 9 files.
- Isolated Playwright: 11 passed; 4 explicitly opt-in live tests skipped.
- Real-backend Playwright: 1 passed; no console errors or unhandled promises.
- Mixed-source audit: 11/11 completion-order invariant; `MIXED-SOURCE CAP VERIFIED`.
- Ruff, Oxlint, TypeScript, and production Vite build: passed.
- Doctor: passed; only expected SearXNG-disabled warning.
- Verify sources: configured public/direct sources probed; current Bluesky external 403 recorded; optional web discovery remained disabled.
- Startup/shutdown/restart smoke: passed; version 1.1.0, content/history/bookmarks/saved searches persisted.
- SQLite integrity, foreign keys, FTS parity, secret scan, and deterministic cache equivalence: passed.

## Known limitations

- Public connector availability is external and variable. During final observation Bluesky AppView returned HTTP 403, GDELT timed out, and GitHub briefly returned anonymous HTTP 403 before a later successful health probe.
- SearXNG is disabled, so X, Threads, and Reddit automated web discovery is unavailable by configuration.
- Exact handles can legitimately produce zero when direct APIs cannot rediscover author posts and web discovery is disabled.
- Cold semantic startup remains expensive because the local multilingual MiniLM runtime initializes on first use. Warm content inference is already cached and bounded.
- Search job cancellation is not exposed; disconnect is safe and bounded work completes. Jobs are local-process state and do not survive an API restart, while completed search sessions remain durable.

## Files changed

| File | Reason and behavior | Coverage |
|---|---|---|
| `apps/api/mirsad_api/services/search_jobs.py` | Bounded job registry, event queue, TTL and safe disconnect behavior | `apps/api/tests/test_search_jobs.py` |
| `apps/api/mirsad_api/routers/search_jobs.py` | Typed job creation and SSE routes | `apps/api/tests/test_search_jobs.py`, live Playwright |
| `apps/api/mirsad_api/services/search.py` | Progress emission, source funnel, terminal consistency and literal identifier admission | `test_search_service.py`, `test_search_jobs.py`, live matrix |
| `apps/api/mirsad_api/services/read_models.py` | Plain snippets, highlight ranges and semantic-only metadata | job/snippet tests, frontend highlight tests |
| `apps/api/mirsad_api/middleware.py` | Correct request-body replay so streaming responses are not held open | SSE completion/disconnect tests |
| `apps/api/mirsad_api/schemas.py` | Typed event/job and result-highlight contracts | API tests and frontend typecheck |
| `apps/api/mirsad_api/main.py` | Job-registry lifecycle and router registration | API/startup tests |
| `apps/api/mirsad_api/config.py` | Bounded job settings and version 1.1.0 | configuration/doctor/startup tests |
| `apps/api/mirsad_api/__init__.py` | Package version 1.1.0 | import/startup smoke |
| `apps/api/mirsad_api/domains/semantic.py` | Timing and bounded-batch instrumentation only | `test_semantic.py` equivalence/cache/batch tests |
| `apps/api/mirsad_api/models.py` | Hot-path session/history indexes | `test_database.py` query-plan test |
| `apps/api/mirsad_api/database.py` | Additive creation of the new indexes | migration and clean-database tests |
| `apps/api/tests/test_search_jobs.py` | Event ordering, capacity, expiry, partial, failure and disconnect regressions | backend suite |
| `apps/api/tests/test_search_service.py` | Identifier collision and retrieval preservation regressions | backend suite |
| `apps/api/tests/test_semantic.py` | Hit/miss/version/batch and exact output equivalence | backend suite |
| `apps/api/tests/test_database.py` | Index presence and planner usage | backend suite |
| `apps/web/src/pages/search-page.tsx` | Three-panel responsive workspace, SSE ownership and session tabs | workflows and Playwright |
| `apps/web/src/components/search/search-form.tsx` | Immediate command bar, automatic-routing disclosure and progressive options | `search-form.test.tsx`, Playwright |
| `apps/web/src/components/search/live-search-trace.tsx` | Accessible bounded live source pipeline | live Playwright and screenshots |
| `apps/web/src/lib/search-job-state.ts` | Discriminated state machine and stale-job guards | `search-job-state.test.ts` |
| `apps/web/src/components/search/result-card.tsx` | Dense result metadata and Explain Score | workflows and Playwright |
| `apps/web/src/components/search/highlighted-snippet.tsx` | React-node-only safe highlighting | `highlighted-snippet.test.tsx` |
| `apps/web/src/lib/api.ts` | Job/SSE client paths and result normalization | workflows, E2E, typecheck |
| `apps/web/src/types/api.ts` | Typed event, phase and snippet models | typecheck and state tests |
| `apps/web/src/lib/i18n.tsx` | Localized workspace, progress, density and explanation strings | frontend tests and RTL Playwright |
| `apps/web/src/components/layout/app-layout.tsx` | Visible application version 1.1 | build and browser smoke |
| `apps/web/src/components/search/search-form.test.tsx` | Progressive disclosure and automatic-routing behavior | Vitest |
| `apps/web/src/components/search/highlighted-snippet.test.tsx` | Safe markup and highlight rendering | Vitest |
| `apps/web/src/lib/search-job-state.test.ts` | Search A/B race and result stabilization | Vitest |
| `apps/web/src/test/fixtures.ts`, `apps/web/src/test/workflows.test.tsx` | Updated typed fixtures and integrated workspace assertions | Vitest |
| `apps/web/e2e/mirsad.spec.ts` | Existing flow compatibility with progressive controls | isolated Playwright |
| `apps/web/e2e/search-evolution-live.spec.ts` | Guarded non-destructive real-backend workflow and screenshots | opt-in live Playwright |
| `apps/web/playwright.config.ts` | Separate isolated and opt-in live projects | Playwright gates |
| `scripts/benchmark_search_evolution.py` | Isolated baseline and stage profiling | baseline JSON |
| `scripts/compare_search_evolution_performance.py` | Controlled before/after comparison | performance JSON |
| `scripts/search_evolution_live_matrix.py` | Bounded non-resetting real API matrix | live-matrix JSON |
| `scripts/audit_mixed_source_cap.py` | Correct all-time fixture scope for order-invariance audit | 11-query audit report |
| `README.md`, `docs/api.md`, `.env.example` | Operator setup, job bounds and SSE contract | doctor and startup smoke |
| `CHANGELOG.md` | Version 1.1 behavior and limitations | release review |
| `package.json`, `package-lock.json`, `apps/web/package.json`, `apps/web/package-lock.json`, `pyproject.toml` | Consistent 1.1.0 metadata and commands | install, test and build |
| `docker-compose.yml`, `tools/browser-capture/manifest.json` | Version-consistent user agent and companion metadata | Compose validation and version scan |
| `reports/search-evolution-baseline.json`, `reports/search-evolution-performance.json`, `reports/search-evolution-live-matrix.json` | Machine-readable controlled and live evidence | JSON validation |
| `reports/search-evolution-screenshots/*` | Desktop, active, completed, partial, explain, RTL and narrow evidence | visual inspection |
| `reports/mixed-source-cap-audit.md`, `reports/mixed-source-cap-audit.json` | Refreshed completion-order evidence | audit command |
| `reports/mirsad-v1.1-search-evolution.md` | Final evidence and release decision | artifact/link/hash validation |

No unrelated architecture or database replacement was introduced.

## Frozen hash verification

| File | Before | After | Assessment |
|---|---|---|---|
| `ranking.py` | `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4` | same | unchanged |
| `semantic.py` | `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24` | `e9b3485af310e6ed87f5e10e609e35496ff48c711a0299032b3f2fd40cdd0701` | instrumentation only; exact cached/uncached equivalence passes |
| `clustering.py` | `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63` | same | unchanged |

Production remains deterministic MAFER Phase 2 with 25% lexical, 75% multilingual MiniLM, semantic top-20, and at most 1% secondary-quality budget. Phase 3 remains shadow-only.

## Operator database integrity before and after

The configured operator path was `/home/smart/MIRSAD/data/mirsad.db`. Before mutation-capable validation it was 6,225,920 bytes with SHA-256 `20e8eefcff3ea0a2b0f303e8fa18de2bb0385138f1abe5b6bf6a1480b378ad3a`, integrity `ok`, zero foreign-key violations, 552 content records, 20 sessions, 572 session-result appearances, 2 bookmarks, 1 saved search, and 464 clusters.

A SQLite-consistent backup was created outside the data path at `/tmp/mirsad-operator-backup-20260821T041833.db`, 6,225,920 bytes, SHA-256 `4bbfca97caf57d82d56219661bdc8d9281bbb393619740676d1be2d8fbaaba39`, and integrity `ok`.

After bounded live searches and the final WAL checkpoint, the original path remains readable at 9,162,752 bytes with SHA-256 `846cb43630d6f2520923ff7d7ecb0241bafbd7ac72b0da7053a8b88ed041b78a`, integrity `ok`, zero foreign-key violations, 785 content and FTS rows, 36 sessions, 855 appearances, 2 bookmarks, 1 saved search, 709 clusters, and 855 cluster memberships. Growth is the expected persisted live-search evidence. No reset or deletion occurred; bookmarks and saved searches are unchanged.

MIRSAD v1.1 SEARCH EVOLUTION VERIFIED
