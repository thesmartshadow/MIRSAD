# MIRSAD v1.0 Functional Hardening

Generated: 2026-08-10 (Asia/Baghdad)  
Release: `1.0.0`  
Production planner: deterministic MAFER Phase 2  
SearXNG in operator profile: disabled

## Executive Assessment

The current application is functionally verified against persisted local state and a bounded 13-case live matrix. The principal operator-visible defect was real: Analytics read only the latest in-memory search snapshot, so a zero-result latest search could make a non-empty database look empty. Analytics now defaults to an explicit `all` scope backed by persisted content, with distinct canonical-content and session-appearance counts. Exact session scopes remain available and identify the selected query and collection time.

The pass also corrected query quoting, partial connector health, no-probe health aggregation, zero-result explanations, persisted bookmark hydration, disabled web-discovery presentation, and startup port ownership. No relevance, semantic, clustering, source-cap, or Phase-3 shadow behavior was changed or promoted.

One validation incident must be recorded: the first production-mode Playwright attempt inherited the fixture suite's destructive `beforeAll` and reset the operator database. The original rows could not be recovered. The E2E harness now unconditionally skips fixture reset whenever any live base URL or live/functional session is supplied. A fresh real Baghdad collection, zero-result identifier session, bookmark, saved search, restart, live guarded E2E, and isolated full E2E were completed after the repair. This was a hardening defect and data-loss incident, not fabricated evidence.

## Confirmed Bugs, Root Causes, And Fixes

| Confirmed bug | Root cause | Fix and evidence |
| --- | --- | --- |
| Global Analytics showed zero after nonzero searches | The page rendered only `currentSearch.analytics`; there was no persisted global read model | Added `GET /api/v1/analytics?scope=all|24h|7d|30d`, defaulted the page to `all`, and added abort/generation guards. Global API and SQLite now agree at 59 content / 59 canonical / 30 appearances. |
| Session and global analytics scope were visually ambiguous | Generic page title did not identify the snapshot source | Added explicit scope selector and session query/time label. The zero-result CVE session correctly shows zero without changing global totals. |
| Average score could treat missing scores as zero | Analytics accepted only numeric scores and averaged the entire corpus | Scores are nullable; averages use only scored records and expose `scored_record_count`. |
| Exact variants could be double quoted | The lattice supplied a quoted exact variant and several connectors wrapped it again | Shared `exact_query_text()` makes quoting idempotent. Live CVE telemetry shows exactly `"CVE-2026-61371"`, never doubled. |
| Bluesky cursor 403 could make a successful first page appear unavailable | Health aggregation ignored retained items when a later page failed | A run with items plus an error is `degraded`, keeps its results, and records `last_success_at`; later success recovers to `healthy`. |
| A no-probe connector health check could erase a prior observed state | Generic/unknown checks overwrote persisted Healthy/Degraded evidence | A no-attempt `unknown` result preserves the last observed operational state. GitHub now performs a bounded `/rate_limit` access probe. |
| X/Threads/Reddit looked generically unavailable with SearXNG off | Presentation collapsed disabled acquisition into connector failure | Source API/UI now reports `web_discovery_disabled` while retaining connector configuration and capability separately. |
| Zero-result searches lacked an actionable reason | Session summaries did not persist an outcome classification | Added `NO_MATCHES`, `NO_MATCHES_IN_TIME_RANGE`, `NO_CAPABLE_SOURCE`, `ALL_SELECTED_SOURCES_FAILED`, and `WEB_DISCOVERY_BLOCKED`, plus external-limit/source-unavailable causes and localized messages. |
| Refreshed result cards lost persisted bookmark state | Result cards initialized bookmark state locally and never read existing bookmarks | Search hydrates bookmark IDs from the backend; a duplicate-create 409 converges to bookmarked state. Unit and live browser checks pass. |
| Live Playwright could reset production data | Fixture initialization was guarded only by one live-session variable | Any live base/session/functional-session now bypasses destructive setup. The guarded live route walk completed without resetting data. |
| Startup could report success against an old process on port 8000/5173 | Readiness checked the port response before proving the newly launched PID owned the service | Startup now refuses occupied owned ports before launch. Occupied-port refusal and clean start/health/stop passed. |

## Analytics Consistency

Machine-readable evidence: `reports/functional-hardening-analytics-validation.json`.

| Scope | Content | Canonical | Appearances | Sources | Duplicate groups | Clusters | Sessions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All collected data, SQLite expected | 59 | 59 | 30 | 2 | 4 | 27 | 2 |
| All collected data, API actual | 59 | 59 | 30 | 2 | 4 | 27 | 2 |
| Baghdad session | 30 | 30 | 30 | 2 | 4 | 27 | 1 |
| CVE session | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

The latest session is the zero-result CVE search, yet global Analytics remains nonzero. Charts use the selected persisted scope, and stale scope requests cannot overwrite a later selection.

## Search / History Consistency

`SearchSession` is authoritative for query, normalized query, status, selected sources, parameters, result/unique counts, duration, warnings, and outcome. The rebuilt persisted sessions are:

| Query | Status | Results | Unique | Duration |
| --- | --- | ---: | ---: | ---: |
| `بغداد` | Partial: GDELT timeout only | 30 | 30 | 5,632 ms |
| `CVE-2026-61371` exact/all-time | Partial: GDELT timeout only | 0 | 0 | 3,800 ms |

History, exact session retrieval, session Analytics, Compare, clusters, and exports read the same persisted session/result links. Compare correctly returned 30 versus 0 for these two sessions.

## Automatic Routing

The frontend sends `source_selection: "auto"`; the backend planner ignores the accompanying compatibility list for selection and records the sources it selected. Manual selection remains exact. The UI now states that MIRSAD selects appropriate healthy sources. A saved automatic Baghdad search survived restart with `source_selection: auto`, `time_range: all`, Balanced mode, and limit 30.

The live automatic matrix selected sources by query intent and retained deterministic fair per-source admission. Completion-order invariance and semantic-opportunity regressions pass in `test_search_service.py` and `test_mafer_intelligence.py`.

## Identifier Search

Both `CVE-2026-61371` over seven days and exact/all-time were executed live. The MAFER lattice classified the original as `IDENTIFIER`, preserved punctuation and case, generated only the safe normalized/exact/identifier forms, and did not interpret `2026` as a historical filter. Connector diagnostics recorded the literal and exactly-once quoted request text.

Both cases returned zero at discovery. RSS and Mastodon fetched records but found no exact match; Bluesky, YouTube, and Hacker News returned no candidate; the all-time GitHub attempt encountered an external HTTP 403. No result reached candidate admission or ranking, so this is not a ranking failure and no synthetic CVE record was inserted.

## Handle / Person Search

`thesmartshadow` is intentionally treated as an ambiguous unprefixed token. `@thesmartshadow` takes the explicit HANDLE/IDENTIFIER path and preserves the `@` form. Both returned zero because working direct/public sources did not rediscover matching author content and SearXNG web discovery was disabled. This limitation is exposed as discovery coverage, not repaired through ranking.

`علي فراس` returned 30 results / 24 unique; one of the judged top five was relevant. `علي فراس محمد رضا` returned six but its judged top five were common-token/name collisions. This observed relevance weakness was documented and not used to alter the frozen ranker.

## Arabic Search

The original Arabic query remains byte-faithful in session state and UI. Derived normalized variants exist only in diagnostics. `وزارة التخطيط` remained the displayed query; no canonical stored content was rewritten to `وزاره`.

Live Arabic coverage included Baghdad, Ministry of Planning, Platform Abwab, artificial intelligence, two person-name forms, hashtag Baghdad, and a diacritized exact phrase. The diacritized `وِزَارَةُ التَّخْطِيط` query retained its original exact representation and returned 30 results. No Arabic normalization or final ranking weights changed.

## Bluesky

The current minimal AppView search probe returned HTTP 200 and `verify-sources` reported `Public AppView search available`. In two live searches, page one returned useful records while a later cursor returned 403; page-one records were retained and the session/source was marked partial/degraded. Subsequent successful searches and the final probe recovered Bluesky to `healthy` with HTTP 200. Configuration and current health remain separate.

## GDELT

GDELT retains a three-second interactive budget, bounded retry behavior, and a circuit breaker. Initial live calls timed out; later matrix cases were short-circuited rather than repeatedly hammering the provider. Healthy source results survived. `verify-sources` passes GDELT configuration because no credential is needed, while runtime search health remains `degraded` with failure category `timeout`; those statements are not conflated.

## GitHub

The all-time CVE attempt observed anonymous HTTP 403 and recorded it as an external limit. The final low-cost `/rate_limit` probe returned HTTP 200 and current GitHub health recovered to `healthy`, with the anonymous lower-quota detail preserved. Temporary access limits do not alter long-term routing utility.

## SearXNG / X / Threads / Reddit

SearXNG remained disabled as requested. X, Threads, and Reddit are displayed as `web_discovery_disabled`, not failed connectors and not direct API search. No CAPTCHA retry, proxy rotation, login automation, or scrape fallback occurred. Manual-import validation remains strict, non-fetching, canonicalized, deduplicated, `MANUAL_IMPORT`, and rejects profile/home/search URLs; deterministic manual-import tests pass.

## Search Zero-Result Explanations

The backend persists the search outcome separately from connector health. The UI distinguishes no matches, possible narrow-time exclusion, no capable source, all sources externally limited, all sources unavailable, and disabled/blocked web discovery. Partial result sessions continue to show successful records and identify only the failed sources.

## All UI Routes

The guarded live Playwright walk covered Search, score explanation, persisted bookmark, History, global/session Analytics, Clusters, Compare, Saved Searches, Bookmarks, Sources, System, Settings, and EN to AR to EN direction changes. It produced no console error or unhandled rejection. The isolated full Playwright suite separately covered real backend persistence on its E2E database, CSV export, cluster members, saved-search replay, bookmark notes, stale-search ownership, desktop/narrow layouts, RTL, and accessibility.

System reports version `1.0.0`; SearXNG degradation does not mark the application failed. Source cards derive configuration, capability, acquisition, health, external state, last check, and safe failure detail from backend metadata without exposing credentials.

## Database Integrity

Final controlled database state:

- 59 content rows and 59 FTS rows.
- 2 sessions and 30 session-result links.
- 27 clusters and 30 cluster-member links.
- 4 duplicate groups.
- 1 bookmark and 1 saved search.
- Zero orphan search results or cluster members.
- `PRAGMA integrity_check = ok`; `PRAGMA foreign_key_check` returned no rows.

## Restart Persistence

Global content, both sessions, clusters, the bookmark, and the automatic saved-search configuration survived API and full stack restarts. A bounded lifecycle script verified `start.sh`, API and web health, nonzero persisted Analytics, runtime logs, `stop.sh`, and PID-file cleanup.

The post-incident empty database was also a clean-state exercise: startup initialized the schema, a real Baghdad search collected YouTube and Bluesky content, a zero-result CVE search was stored, and subsequent restarts preserved the state.

## Live Query Matrix

Full telemetry: `reports/functional-hardening-live-matrix.json`. The untouched pre-reset copy is `reports/functional-hardening-live-matrix-pre-reset.json`.

| Case | Query | Range / exact | Status | Results / unique | Clusters | Duration | Outcome / stop |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Baghdad | `بغداد` | 7d / no | Completed | 30 / 30 | 26 | 2,613 ms | Results / user limit |
| Ministry | `وزارة التخطيط` | 7d / no | Partial | 4 / 4 | 4 | 5,323 ms | Results / max rounds |
| Abwab | `منصة ابواب` | 7d / no | Partial | 3 / 3 | 3 | 4,784 ms | Results / max rounds |
| Arabic AI | `الذكاء الاصطناعي` | 7d / no | Partial | 30 / 30 | 30 | 3,275 ms | Results / user limit |
| Mixed entity | `Microsoft العراق` | 7d / no | Partial | 0 / 0 | 0 | 2,155 ms | No matches / low gain |
| CVE recent | `CVE-2026-61371` | 7d / no | Partial | 0 / 0 | 0 | 1,761 ms | No matches / low gain |
| CVE exact | `CVE-2026-61371` | all / yes | Partial | 0 / 0 | 0 | 1,637 ms | No matches / low gain |
| Handle text | `thesmartshadow` | 7d / no | Partial | 0 / 0 | 0 | 1,605 ms | No matches / low gain |
| Handle | `@thesmartshadow` | 7d / no | Partial | 0 / 0 | 0 | 1,343 ms | No matches / low gain |
| Hashtag | `#بغداد` | 7d / no | Partial | 2 / 2 | 2 | 2,183 ms | Results / low gain |
| Person | `علي فراس` | all / no | Partial | 30 / 24 | 20 | 3,253 ms | Results / user limit |
| Full person | `علي فراس محمد رضا` | all / no | Partial | 6 / 6 | 6 | 2,747 ms | Results / max rounds |
| Diacritized exact | `وِزَارَةُ التَّخْطِيط` | all / yes | Partial | 30 / 30 | 28 | 4,013 ms | Results / user limit |

The matrix made 125 bounded connector requests and produced 135 displayed results across cases. Twelve sessions were partial because GDELT timed out/circuit-opened and four also observed Bluesky cursor 403; partial failures did not discard healthy results.

## Per-Source Telemetry

Aggregated across the live matrix:

| Source | Requests | Fetched | Matched | Admitted | Persisted-stage | Final top results | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bluesky | 21 | 124 | 87 | 87 | 87 | 44 | 4 cursor/transport observations |
| YouTube | 37 | 411 | 159 | 121 | 121 | 87 | 0 |
| GitHub | 10 | 40 | 20 | 20 | 20 | 4 | 1 HTTP 403 |
| Mastodon | 16 | 640 | 0 | 0 | 0 | 0 | 0 |
| RSS | 18 | 414 | 0 | 0 | 0 | 0 | 0 |
| Hacker News | 19 | 3 | 0 | 0 | 0 | 0 | 0 |
| GDELT | 4 attempted | 0 | 0 | 0 | 0 | 0 | 12 timeout/circuit observations |

Fetched records are not presented as matches. Repeated round-stage persisted counts in this table are telemetry contributions, not unique database rows.

## Operator Judgments

The observational sanity artifact is `reports/functional-hardening-operator-judgments.json`. It contains 25 `RELEVANT` and 9 `NOT_RELEVANT` labels; zero-result cases were not assigned fabricated labels. Baghdad, Arabic AI, hashtag, Abwab, and the diacritized ministry case were visibly on-topic. The full personal-name case exposed common-token collisions and remains a documented ranking-quality limitation; no tuning used these labels.

## Performance

- Live API duration: 1,343 to 5,323 ms; median 2,613 ms; mean 2,822 ms.
- Live caller wall time: median 2,688 ms.
- Rebuilt Baghdad trace: planning 7 ms, connector collection 4,324 ms, persistence 45 ms, deduplication 144 ms, ranking 983 ms including 904 ms semantic reranking, clustering 111 ms, total 5,632 ms.
- GDELT never exceeded its configured bounded behavior; its circuit breaker prevented repeated long waits.
- The global cap was applied after fair per-source admission; source completion/request order invariance tests pass.

## Failure Isolation

Deterministic tests cover GDELT timeout/circuit, Bluesky later-page 403 and recovery, GitHub 403/rate limit and recovery, SearXNG unavailable/all engines blocked, YouTube error, Mastodon `AUTH_REQUIRED`, malformed connector records, and partial-source failure. Live evidence separately exercised GDELT timeout/circuit, Bluesky cursor degradation/recovery, and GitHub external 403/recovery. Healthy results remained visible.

## Security

The full backend suite revalidated fixed-host connector calls, SearXNG/Common Crawl/oEmbed boundaries, URL classifiers, private/loopback rejection, redirects, Unicode domains, raw HTML handling, manual import, feedback validation, SQL parameterization, and CSV formula protection. Browser capture performs no target fetch and transfers no cookies or credentials. The production frontend bundle contains zero configured secret values. CORS and localhost defaults remain unchanged. No CAPTCHA bypass or login automation was introduced.

## Tests

| Gate | Result |
| --- | --- |
| Backend | 205 passed |
| Frontend Vitest | 24 passed |
| Guarded live Playwright | 1 passed |
| Full isolated Playwright | Passed; 3 opt-in live tests skipped without live variables |
| Ruff / frontend lint | Passed |
| TypeScript | Passed |
| Production build | Passed |
| Doctor | All internal checks passed; expected SearXNG warning |
| `verify-sources` | Bluesky, HN, GitHub, GDELT config, RSS config, YouTube, Mastodon passed |
| SQLite / FTS | Integrity clean; 59/59 parity |
| Startup / shutdown | Clean ownership, health, logs, persistence, and PID cleanup passed |
| Secret scan | 1 configured secret value checked; 0 frontend bundle hits |
| Frozen ranker hashes | Exact match |

## Known External Limitations

- SearXNG is disabled, so X/Threads/Reddit web-index discovery is unavailable by configuration.
- GDELT was search-time degraded by timeouts despite credential-free configuration being valid.
- GitHub anonymous access can receive temporary HTTP 403/rate limits.
- Bluesky may return a later-page cursor 403; successful earlier pages are retained.
- Direct/public sources did not rediscover the tested handles or CVE during the bounded campaign.
- Mastodon public-timeline coverage is instance-scoped and returned no local matches for these queries.

## Known Internal Limitations

- Unprefixed handle-like tokens remain ambiguous; operators should use `@handle` when handle intent is known.
- Full Arabic person names can still collide on common name tokens. This is recorded evidence, not tuned during hardening.
- Global Analytics describes persisted content; it cannot retroactively reconstruct deleted pre-hardening sessions.
- The test-harness reset incident destroyed the prior operator database. The guard is fixed, but recovery requires an external backup because no pre-reset snapshot existed.

## Files Changed

- Backend: analytics domain/router/read model/schema; search outcome and health aggregation; connector exact-query handling; Bluesky/GitHub behavior; resource availability presentation.
- Frontend: Analytics scope and charts; Search zero/partial/automatic-source presentation; source state presentation; bookmark hydration; localization and API types.
- Operations: `start.sh` port-ownership refusal; Playwright live-mode isolation.
- Tests: functional-hardening backend suite, connector/startup regressions, Analytics/Form/ResultCard tests, guarded live E2E.
- Evidence/docs: live matrix, operator judgments, analytics validation, this report, `README.md`, and `docs/api.md`.

## Frozen Hash Verification

| File | Before and after SHA-256 |
| --- | --- |
| `ranking.py` | `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4` |
| `semantic.py` | `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24` |
| `clustering.py` | `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63` |

MIRSAD v1.0 FUNCTIONALLY VERIFIED
