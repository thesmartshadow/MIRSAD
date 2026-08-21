# MIRSAD Final Independent Verification

Generated 2026-08-09 (Asia/Baghdad). This report records fresh source inspection, test execution,
runtime probes, database checks, browser automation, live-source calls, clean-install work, and
Docker execution. Earlier reports were treated as claims and traced back to code or runtime behavior.

## Repository Revision

The repository cannot provide a revision identifier. `.git/` is an empty directory, and
`git status`, `git diff --stat`, `git diff`, and `git log -1` all return
`fatal: not a git repository`. This is `NOT_PROVEN`, not a clean-worktree claim. Version metadata
is consistently `1.0.0-rc1` in the root/web packages and runtime, with the PEP 440 equivalent
`1.0.0rc1` in Python packaging.

## Verification Method

- Read all production domains, routers, connector registrations, Pydantic/TypeScript schemas,
  frontend routes/providers, SQL schema/FTS triggers, scripts, tests, Docker files, README, and docs.
- Established the Phase A read-only baseline in
  `reports/final-requirement-verification.md` before changing production code.
- Reproduced failures with direct domain/service/SQLite/browser probes, fixed only proven defects,
  and added regression coverage.
- Ran deterministic tests without credentials, supplemental public-network probes separately, and
  independently recomputed IR metrics from ranked IDs and raw judgments using `jq`.

## Requirement Traceability

| ID | Requirement | Code evidence | Test/runtime evidence | Status | Result |
| --- | --- | --- | --- | --- | --- |
| R01 | Revision and dirty state known | Empty `.git/` | All required Git commands fail | NOT_PROVEN | No revision can be certified. |
| R02 | v1.0.0-rc1 consistent | `package.json`; `config.py:Settings.version` | Build and `/system` report rc1 | PASS | PEP 440 Python form is equivalent. |
| R03 | Monorepo/domain separation | `apps/web`; `apps/api/mirsad_api/{connectors,domains,services,routers}` | Import/test and route inventory | PASS | Architecture remains separated. |
| R04 | shadcn-only UI | `components.json`; `components/ui`; package/import graph | Prohibited-framework scan; build | PASS | SHADCN UI POLICY: PASS. Recharts is composed inside `ChartContainer`. |
| R05 | No external LLM dependency | Deterministic query/ranking/dedup/clustering domains | Runtime-symbol repository scan | PASS | Only documentation says that LLMs are not used. |
| R06 | Connector inventory registered | `services/registry.py:build_connector_registry()` | Doctor and source metadata API | PASS | Fifteen production connectors; mock is opt-in. |
| R07 | Capability metadata/taxonomy | `connectors/base.py:ConnectorCapabilities` | Social/API/form tests | PASS | Selector derives behavior from API metadata. |
| R08 | Capability honesty | Per-connector metadata; restricted adapters | `test_restricted_global_search_and_platform_specific_reach` | PASS | Telegram/Mastodon/Instagram/TikTok/Facebook/LinkedIn/X scopes are bounded. |
| R09 | Credential security | `config.py`; registry; public source schema | Bundle/env/log/source-verifier scans | PASS | No secret values or credential fields reach the browser. |
| R10 | Distinct source states | `BaseConnector`; `SearchService._health_state()`; `StatusBadge` | 401/403/429/5xx/timeout tests and Sources UI | PASS | Empty, partial, unconfigured, restricted, unavailable, timeout, and rate-limit states remain distinct. |
| R11 | RSS stage correctness | `RssConnector.search_with_options()` | Live positive `Hormuz`: 30/30/1/1/1; absent-token negative: 30/30/0/0/0 | PASS | 90/90/0 means query exclusion, not normalization failure. The positive API session persisted one unique record. |
| R12 | GDELT three-second budget | `GdeltConnector.search()` wraps the retry loop in `asyncio.timeout()` | Monotonic deterministic budget test; live 3001.62 ms, 3002.17 ms, then 0.01 ms/open circuit | PASS | The two ~3 s values are separate searches. A single search has one total budget that includes retries/backoff. |
| R13 | Connector concurrency | `SearchService.execute():asyncio.gather` | Three 50 ms fixtures: 78.26 ms median; fast/medium/slow source completion 32.52/92.70/182.92 ms | PASS | Runtime follows the slowest bounded connector plus engine overhead. |
| R14 | Stale-request protection | `search-page.tsx:runSearch()` generation/abort guard | `a completed stale search cannot redirect...` | PASS | Route-away late completion cannot navigate or overwrite state. |
| R15 | Unified nullable content | `ConnectorItem`; ORM/schema/TS result types | Social normalization/persistence tests | PASS | Unknown public metrics remain null, not zero. |
| R16 | UTC persistence | `models.py:UTCDateTime` | `test_sqlite_datetime_round_trip_is_aware_utc`; live JSON `Z` values | PASS | SQLite reload restores aware UTC. |
| R17 | Query intent processing | `domains/query.py:process_query()` | query intent/control tests | PASS | Keyword, phrase, hashtag, handle, URL, mixed language are deterministic. |
| R18 | Conservative Arabic normalization | `normalize_arabic()`; `normalize_text()` | positive/adversarial non-match tests | PASS | Bounded letter/digit/control normalization; no synonym drift. |
| R19 | Arabic FTS/BM25 | normalized content columns and six-column FTS triggers | Arabic FTS regression; direct insert/update/rebuild/delete | PASS | Normalized Arabic forms contribute BM25 without replacing source text. |
| R20 | Candidate boundary quality | `SearchService._candidate_strength()` | `test_global_candidate_limit_retains_strongest_lexical_matches` | PASS | Strong exact candidate is retained before the request limit. |
| R21 | Language filtering | `resolve_content_language()`; common eligibility | unknown-language and GitHub regressions | PASS | `und` no longer bypasses a requested language. |
| R22 | Time filtering | common pipeline publication-time check | `test_common_pipeline_rejects_known_old_results` | PASS | Connector date parameters are hints; backend is authoritative. |
| R23 | Candidate generation versus ranking | `ranking.py:is_candidate_match()`; search orchestration | boundary/ranking tests | PASS | Candidate recall boundary and final scoring are distinct. |
| R24 | Authoritative formula | `ranking.py:calculate_score()` | `test_explainable_score_matches_weighted_formula` | PASS | Backend explanation is authoritative. |
| R25 | Relevance gate | squared supporting factor in `calculate_score()` | weak-popular/fresh/cross-source regressions | PASS | Supporting signals cannot rescue weak relevance. |
| R26 | Component distributions | `quality.py:_component_statistics()`; blinded holdout evaluator | Holdout reports min/p10/p25/median/mean/p75/p90/max/stddev | PASS | Source confidence stddev 16.57, cross-source 19.30, novelty 24.27; no longer constant. |
| R27 | Correct IR metrics | `quality.py:_evaluate_cases()` | Independent `jq` recomputation | PASS | Standard and returned-set precision are now named separately. |
| R28 | Evaluation independence | separate `blinded_holdout_documents.json` and `blinded_holdout_judgments.json` | `npm run evaluate:holdout`; three holdout regressions | PASS | 110 documents, 16 queries, at least 12 candidates/query; current ranking ran unchanged before any tuning. |
| R29 | Language-specific metrics | `quality.py:_language_metrics()` | Arabic/English/mixed standard metrics regenerated | PASS | Aggregate-only reporting was corrected. |
| R30 | Deterministic ordering | stable score/time/source/external-ID key | completion/input-order tests | PASS | Async completion cannot change logical tie order. |
| R31 | Engagement calibration | `domains/engagement.py:PLATFORM_SCALES` | 0 through 1,000,000; missing/bool tests | PASS | Finite, monotonic, platform-specific, null-safe. |
| R32 | Freshness decay | `freshness_score()` half-life formula | 10m through 1y regression | PASS | Monotonic, bounded 48-hour default half-life. |
| R33 | Deduplication | URL/fingerprint/complete-link near-text stages | adversarial dedup tests | PASS | False transitive merge is prevented; originals remain. |
| R34 | Duplicate/cluster separation | `find_duplicate_groups()`; `cluster_items()` | canonical duplicate cluster regression | PASS | Identity and same-story grouping are separate but coherent. |
| R35 | Story clustering | title/body deterministic blocking | specific-event versus broad-topic test | PASS | Judged cluster pair precision/recall are 1.0/1.0. |
| R36 | Independent cross-source presence | unique source set per duplicate group | dedup/social analytics tests | PASS | Twenty X posts count as one platform. |
| R37 | Social Reach | `engagement.py:social_reach()` | social analytics tests/UI wording | PASS | Deterministic distribution metric, never truth/reliability. |
| R38 | Trends/time buckets | `analytics.py:time_buckets()`; `trend_indicator()` | 15m/7d/all-time regressions | PASS | Chronology and zero baseline are correct. |
| R39 | Real stored analytics | search analytics snapshot pipeline | acceptance/social analytics tests | PASS | No production placeholder values found. |
| R40 | Related terms | Arabic/English stopwords and document frequency | analytics tests/source inspection | PASS | URLs, query tokens, punctuation, repetition removed. |
| R41 | One locale/direction owner | `I18nProvider`; `DirectedApplication` | provider and Playwright DOM assertions | PASS | Locale drives html lang/dir and DirectionProvider. |
| R42 | Immediate switching | synchronous `setLocale()` document update | EN/AR/EN and 20-toggle browser tests | PASS | No reload or route change needed. |
| R43 | 20-switch stress across routes | shared provider | Search, loaded Results, Analytics, Settings: five each | PASS | Routes remained stable; no console errors. |
| R44 | State preserved on locale switch | `SearchStateProvider`; form initial request | loaded-session browser regression | PASS | Query/results/filter/sort/session retained; no search rerun. |
| R45 | Portal direction matrix | root DirectionProvider; production imports of Dialog/Sheet/Dropdown/Select/Tooltip | explicit EN -> AR -> EN portal matrix | PASS | Every portal primitive imported by production passed direction, alignment, keyboard, focus entry/return, and close behavior. Command/Popover are unused wrappers. |
| R46 | Sidebar desktop/mobile RTL | direction-driven `side`; logical CSS | collapsed stress plus mobile right-side open/Escape close | PASS | Desktop and narrow states are direction-correct. |
| R47 | Mixed bidi content | result/bookmark/report use `dir="auto"` | RTL fixture/browser checks | PASS | URLs/technical values remain isolated LTR. |
| R48 | Localization completeness | `lib/source-presentation.ts`; bilingual source/error keys | unit tests and Arabic Search/Sources Playwright assertions | PASS | Application-owned coverage, configuration, warning, and failure prose is localized; brands/technical identifiers remain canonical. |
| R49 | Cold locale startup | early script in `index.html` | persisted Arabic and English deep-route loads | PASS | No harmful wrong-direction application render observed. |
| R50 | Accessibility | semantic labels/shadcn focus primitives | Axe Search/Sources/Settings in EN and narrow AR | PASS | No serious/critical findings in tested routes. |
| R51 | Frontend state ownership | locale/theme/search providers; form-local draft | state-preservation browser tests | PASS | No competing direction/search-session owners observed. |
| R52 | API contract alignment | Pydantic schemas and `types/api.ts` | API/social/nullability tests | PASS | Optional metrics, enums, timestamps, and source types align. |
| R53 | DB/FTS integrity | models, constraints, FTS triggers | direct lifecycle plus tests | PASS | Post-live DB: integrity ok, FK clean, content=FTS=25. |
| R54 | History/bookmark lifecycle | `data_management.py:clear_history()` | operational API regression | PASS | Bookmark content/note survive history clear. |
| R55 | Export correctness/safety | `services/exporting.py` | BOM/formula/API tests and live exports | PASS | Arabic/null/newline fields safe; no path parameter. |
| R56 | Saved searches | saved-search service/router/UI | CRUD/rerun API and Playwright | PASS | Full configuration persists; no monitoring semantics. |
| R57 | Bookmarks | bookmark models/service/UI | note/edit/delete/history interaction tests | PASS | Original retrieved content is not modified. |
| R58 | Search diagnostics | connector runs/session diagnostics | RSS/telemetry/API/UI tests; live connector counts | PASS | Fetched, valid, matching, normalized, final, attempts, phases are distinct. |
| R59 | Internal/live performance separated | benchmark and live verifier scripts | separate artifacts and commands | PASS | Fixture timings are not presented as Internet latency. |
| R60 | Scaling bounded | result cap and benchmark | 100/200 dedup; ranking through 10,000 | PASS | Quadratic duplicate work is bounded to 200 interactive candidates. |
| R61 | Memory/resource sanity | bounded requests/pagination | 31-search/200-result VmRSS snapshots; 20-switch/overlay/route browser CDP snapshots | PARTIAL | Backend RSS range was 4,256 KiB; post-GC browser heap decreased 24.18 MB to 23.04 MB. This is bounded observation, not a formal leak proof. |
| R62 | Pagination integrity | stored session rank; frontend slicing | workflow/source inspection | PASS | Pages do not rerank or refetch. |
| R63 | Error isolation/classification | `BaseConnector`; `_run_connector()` | 401/403/429/500/timeout/malformed/empty tests | PASS | Healthy records survive failed peers. |
| R64 | Multi-request telemetry | context-local aggregate diagnostic helpers | X/GitHub/YouTube/Threads/Reddit tests | PASS | Pagination/token/statistics requests no longer reset counters. |
| R65 | verify-sources | `scripts/verify_sources.py` | Fresh command exit 0 | PASS | Safe PASS/WARN/FAIL; optional absence is not app failure. |
| R66 | doctor | `scripts/doctor.mjs` | Fresh command, every required check PASS | PASS | Versions, FTS, dirs, deps, DB, connectors are actually probed. |
| R67 | startup scripts | `start.sh`; `stop.sh` | combined start/probe/duplicate/stop and occupied-port tests | PASS | Localhost readiness and strict ports verified. |
| R68 | optional Docker | Dockerfiles/Compose/ignore files | Build, up, 200 probes, restart persistence, down | PASS | Production preview and API bind localhost; named volume persists. |
| R69 | fresh installation | `scripts/install.sh` | isolated source-only install/test/build/doctor | PASS | Installer now creates ignored runtime directories. |
| R70 | production build | Vite/TS config | 2,769 modules transformed | PASS | Build exits zero and Docker preview serves routes. |
| R71 | suite integrity/counts | pytest/Vitest/Playwright configs | 87 backend, 12 frontend, 11 E2E pass, 1 live skip | PASS | Skip is explicitly opt-in live access, not hidden deterministic coverage. |
| R72 | complete route crawl | `App.tsx` route table | 10 routes EN desktop and AR narrow | PASS | No uncaught errors or missing-route failures. |
| R73 | no fake production data | mock flag defaults false and conditional registry | config/registry scan | PASS | Fixture connector requires explicit test/dev enablement. |
| R74 | live provenance path | connector/search/read/export/frontend pipeline | Fresh live API/export session plus opt-in persisted-session browser workflow | PASS | Real HN/GitHub records retain links/text/provenance. |
| R75 | external content/link safety | `safeExternalUrl()`; text rendering; safe rel | frontend tests/source scan/live link check | PASS | No retrieved content enters raw HTML. |
| R76 | server-side fetch safety | exact parsed host check; server-only RSS URLs | host/config/API inspection | PASS | Users cannot supply connector/RSS fetch URLs. |
| R77 | settings validation | settings Pydantic/router validators | sum/type/bool/range/reset tests | PASS | Backend rejects invalid weights including booleans. |
| R78 | audit events | search/settings/data event writes | live DB event inspection | PASS | Start/completion/failure/rebuild are timestamped and secret-free. |
| R79 | documentation truth | README/docs/current reports | code-to-doc comparison | PASS | Pipeline, FTS, metrics, counts, Docker, credentials corrected. |
| R80 | credential matrix | `docs/social-credentials.md`; config/registry | variable-by-variable code comparison | PASS | Fields/refresh/approval behavior match implementation. |
| R81 | three live social connectors | credentialed adapters/public Bluesky | No credentials; Bluesky HTTP 403 | BLOCKED_EXTERNAL | Engineering ready, social pilot awaits legitimate access. |
| R82 | live supplemental sources | HN/GitHub/RSS/GDELT adapters | Fresh live verifier and live API session | PASS | HN/GitHub healthy; RSS healthy; GDELT bounded degraded. |
| R83 | GitHub scopes | repositories/issues/PR adapter | normalization/partial-scope tests; live repo access | PASS | Code search remains off by default. |
| R84 | social analytics/platform presence | analytics and cluster persistence | social end-to-end fixtures | PASS | Derived from stored records only. |
| R85 | local security posture | `main.py`; config; startup | headers/CORS/request/error tests | PASS | Local binding, body limits, generic 500, security headers. |
| R86 | search validation | `schemas.py:SearchRequest` | blank/punctuation/oversize/bounds tests | PASS | Query 300 and result 200 limits are authoritative. |
| R87 | print report | report route/page | browser print workflow | PASS | Stored data only; browser Print/Save as PDF. |
| R88 | source progress/partial UX | pending/final source list and warnings | partial search browser workflow | PASS | REST is non-streaming by design; bounded sources remain individually visible. |

## Issues Found Before Fixes

The read-only phase reproduced seven High correctness failures: naive SQLite timestamps, language
filter bypass, absent common time filtering, pre-ranking candidate loss, Arabic-normalized FTS loss,
misnamed Precision@K, and stale route navigation. Medium failures included reset-per-request
connector telemetry, duplicate/cluster incoherence, boolean weights, weak cluster recall, a
timeout-only GDELT breaker, clean-install directory failure, and incomplete localization. Low
findings were prefix host validation, stale RTL component metadata, and oversized Docker context.

## Fixes Applied

- Added UTC-normalizing ORM datetimes and offset round-trip coverage.
- Enforced resolved language and known publication-time filters in the common search pipeline.
- Ranked candidate strength before limiting and indexed normalized Arabic text separately.
- Split standard Precision@K from returned-set precision and independently recalculated judgments.
- Added route-unmount abort/generation ownership and loaded-session language preservation.
- Aggregated multi-request telemetry and extended GDELT breaker failures to network/upstream errors.
- Kept canonical duplicates in one story cluster and tuned story clustering against judged pairs.
- Rejected boolean ranking weights, tightened exact host allowlisting, enabled shadcn RTL metadata.
- Made clean install create runtime directories and reduced Docker build context.
- Added full bilingual route, mobile sidebar, multi-route 20-switch, and Arabic accessibility tests.

## Algorithm Verification

The authoritative score is
`0.35R + gate*(0.20F + 0.15E + 0.10SC + 0.10CP + 0.10N) - penalty`, where
`gate=(R/100)^2`. Independent hand calculations match backend values. Regression cases prove an
old/quiet highly relevant item beats a fresh/viral weak collision, an exact phrase beats a weak
high-confidence title collision, and repeated cross-platform irrelevance is not rescued.

## Search Quality Independent Recalculation

The fresh evaluator and a separate `jq` calculation over ranked IDs/judgments agree:

| Slice | Standard P@5 | Standard P@10 | Returned-set P@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Primary, 20 queries | 0.2500 | 0.1250 | 1.0000 | 1.0000 |
| Hard, 15 judged retrieval queries | 0.2800 | 0.1400 | 0.8333 | 0.9222 |
| Arabic primary | 0.2286 | 0.1143 | 1.0000 | 1.0000 |
| English primary | 0.2667 | 0.1333 | 1.0000 | 1.0000 |
| Mixed primary | 0.2000 | 0.1000 | 1.0000 | 1.0000 |
| Exact phrase primary | 0.2857 | not separately reported | 1.0000 | not separately reported |

The hard evaluation has one explicit no-relevance query excluded from standard IR averages. Primary
candidate pools contain only one or two results (mean 1.25 relevant and returned documents), which
explains P@5 `0.2500`, P@10 `0.1250`, and MRR `1.0000`: fixed-K precision measures all K slots,
while MRR only measures the first relevant rank. The hard set averages 1.40 relevant and 1.87
returned documents; 13/15 first relevant results are rank one, producing P@5 `0.2800`, P@10
`0.1400`, and MRR `0.9222` without a metric error.

The new frozen holdout stores 110 documents separately from 16 judgment records and returns at least
12 lexical candidates for every query. Ranking constants were not changed after the baseline:

| Holdout slice | Queries | P@5 | P@10 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Arabic | 5 | 0.0000 | 0.3000 | 0.1286 |
| English | 8 | 0.0000 | 0.2000 | 0.1181 |
| Mixed Arabic/English | 3 | 0.1333 | 0.3333 | 0.4286 |
| Exact phrase | 6 | 0.0000 | 0.2500 | 0.1234 |
| Ambiguous | 2 | 0.0000 | 0.2500 | 0.1340 |
| Hard | 10 | 0.0400 | 0.2600 | 0.2133 |
| Overall | 16 | 0.0250 | 0.2562 | 0.1796 |

These low dense-holdout values are retained rather than tuned away. Nearly all holdout candidates
contain the identical full query phrase, causing lexical relevance to saturate (median 100) and
leaving recency/engagement to order semantically different name collisions. This is a real bounded
limitation of deterministic lexical retrieval, not an implementation or metric failure. The
holdout is credible regression evidence but not an assessor-blind academic evaluation.

## Arabic Retrieval Verification

Tests cover diacritics, tatweel, Alef forms, Arabic/Persian digits, punctuation, whitespace, format
controls, hashtags, mixed strings, organization names, proper nouns, and adversarial non-matches.
The FTS lifecycle directly matched normalized `وزاره` against original `وزارة`, updated terms
without stale matches, survived rebuild, and removed the row on deletion.

## English Retrieval Verification

Phrase, title, proximity, hashtag/handle/URL intent, weak collisions, old relevant items, and popular
irrelevant items are judged. Ambiguous broad terms remain the principal deterministic lexical risk;
no unmeasured semantic dependency was enabled.

## Hard Query Evaluation

Standard hard P@5/P@10 do not change between legacy and current pipelines because K exceeds the
small candidate sets. Returned-set P@5 improves 0.6711 to 0.8333 and MRR improves 0.8022 to 0.9222.
Residual errors are retained in `reports/relevance-improvement.md` rather than hidden.

## Ranking Calibration

| Signal | Min | P10 | P25 | Median | Mean | P75 | P90 | Max | Stddev |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Final | 31.69 | 43.80 | 57.67 | 74.80 | 66.58 | 75.83 | 77.11 | 82.11 | 12.50 |
| Relevance | 77.50 | 100.00 | 100.00 | 100.00 | 98.39 | 100.00 | 100.00 | 100.00 | 5.79 |
| Freshness | 0.00 | 0.00 | 8.84 | 95.08 | 64.06 | 98.57 | 98.57 | 98.57 | 42.48 |
| Engagement | 0.00 | 3.00 | 8.00 | 77.00 | 55.23 | 93.00 | 98.50 | 100.00 | 40.75 |
| Source confidence | 39.00 | 41.00 | 45.00 | 60.00 | 61.16 | 75.00 | 85.00 | 91.00 | 16.57 |
| Cross-source | 0.00 | 0.00 | 0.00 | 0.00 | 12.56 | 30.00 | 45.00 | 60.00 | 19.30 |
| Novelty | 12.00 | 20.00 | 28.00 | 36.50 | 45.48 | 75.00 | 82.00 | 92.00 | 24.27 |
| Spam penalty | 0.00 | 0.00 | 0.00 | 0.00 | 0.05 | 0.00 | 0.00 | 5.00 | 0.50 |

The variable rows above come from the independent holdout; the original hard fixture remains frozen
and constant for those three signals. Distributions now prove that each configured signal varies and
remains bounded without altering the production weights.

## Deduplication Verification

Judged duplicate pair precision/recall are 1.0/1.0. Tracking parameters, URL variants, normalized
fingerprints, punctuation changes, tiny edits, malformed URLs, and transitive false-merge cases pass.
Duplicate groups preserve originals and remain distinct from story clusters.

## Clustering Verification

Judged story pair precision/recall are 1.0/1.0. Canonical duplicates co-cluster, paraphrased reports
of one specific event cluster, and same-organization/broad-topic reports remain separate. Input order
does not change membership or representative selection.

## Analytics Verification

Deterministic sessions validate totals, unique/duplicate counts, platform/language/category
distributions, cluster counts, score buckets, Social Reach nullability, trends, and full fixed/all-time
windows. Production charts consume stored analytics and return empty states instead of sample data.

## Arabic / English Switching Verification

Root cause was split timing/state: persisted locale was applied after initial render while sidebar
and overlay layout used physical LTR placement. Locale now initializes before React, and one provider
drives document lang/dir, DirectionProvider, layout, and portals synchronously.

## RTL / LTR Runtime Evidence

Playwright passes immediate EN/AR/EN, 20 switches on Search, and another 20 distributed over Search,
loaded Results, Analytics, and Settings. Query, results, exact filter, sort, session, route, sidebar
collapse, and theme remain stable without external reruns. A narrow Arabic mobile sidebar opens on
the right with `dir=rtl` and closes by keyboard. Ten routes load in English desktop and Arabic
narrow layouts. Dialog, Sheet, Dropdown, Select, and Tooltip each pass an explicit EN -> AR -> EN
direction/alignment/keyboard/focus-return matrix. Application-owned connector prose switches
immediately while canonical platform brands remain unchanged. Axe reports no serious/critical
issues on Search/Sources/Settings in both languages.

## Connector Verification

Final `verify-sources`: Hacker News PASS 1,680 ms; GitHub PASS 253 ms; Bluesky FAIL HTTP 403
318 ms; all optional credentials are WARN; Facebook/LinkedIn/TikTok remain restricted; command exit
is zero because no local implementation failed. No secrets appeared.

Fresh `verify:live`:

| Source | State | Fetched | Matched | Normalized | Aggregate latency | Limitation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| X | unconfigured | 0 | 0 | 0 | 0 ms | Bearer token absent |
| Threads | unconfigured | 0 | 0 | 0 | 0 ms | Access token absent |
| Telegram | unconfigured | 0 | 0 | 0 | 0 ms | Public-channel session absent |
| Reddit | unconfigured | 0 | 0 | 0 | 0 ms | Approved OAuth credentials absent |
| YouTube | unconfigured | 0 | 0 | 0 | 0 ms | API key absent |
| Bluesky | unavailable | 0 | 0 | 0 | 1,015 ms | HTTP 403 |
| Mastodon | unconfigured | 0 | 0 | 0 | 0 ms | Instance/token absent |
| Instagram | unconfigured | 0 | 0 | 0 | 0 ms | Approved hashtag access absent |
| TikTok | restricted | 0 | 0 | 0 | 0 ms | Research approval/credentials required |
| Facebook | restricted | 0 | 0 | 0 | 0 ms | No global public-post search |
| LinkedIn | restricted | 0 | 0 | 0 | 0 ms | No global public-post search |
| Hacker News | healthy | 20 | 20 | 20 | 3,140 ms | None observed |
| GitHub | healthy | 17 | 17 | 17 | 1,783 ms | Anonymous lower rate limit |
| GDELT | degraded | 0 | 0 | 0 | 6,004 ms over 3 probes | Two separate bounded searches, then open circuit |
| RSS | healthy | 90 | 0 | 0 | 1,325 ms | Probe terms absent from feed |

The fresh unified live API session completed in 1,458 ms with 25 records (GitHub 19, Hacker News 6),
23 unique results, 20 clusters, and one truthful Bluesky warning. JSON export was 52,303 bytes; CSV
was 14,599 bytes with `EF BB BF`; all result links passed HTTP(S) validation.

## RSS Verification

The connector exposes fetched, schema-valid, query-matching, time-eligible, malformed, normalized,
and final counts. The current BBC feed supplied the term `Hormuz`: the API session recorded 30
fetched, 30 valid, 1 matching, 1 normalized, 1 persisted, and 1 unique result in 372.7 ms. The same
captured live XML with an absent token recorded 30 fetched/valid and zero matching/normalized. The
fixed three-probe run recorded 90 fetched, 90 valid, zero matching, and zero malformed because none
of those exact probe terms occurred in the current feed.

## GDELT Budget Verification

The live verifier measured two HTTP attempts inside a 3,001.62 ms connector search, then two attempts
inside a separate 3,002.17 ms search that opened the breaker; the next search returned in 0.01 ms
with zero attempts. The first two figures are separate calls, not a six-second retry loop. A
monotonic deterministic run measured attempt durations 20.14/20.14 ms, 250.49 ms backoff, and
291.15 ms total inside a 350 ms connector budget; the second call opened the circuit and the next
response took 0.007 ms. Tests allow scheduling tolerance and assert the total budget rather than one
exact millisecond value.

## Security / Secret Handling

`.env` is absent and ignored; `.env.example` contains placeholders. Production bundle scans find
no credential variable names or bearer-like values. Source/status APIs expose only configuration
state. URLs are parsed against exact fixed origins, RSS URLs are server configuration only, external
content is text, links accept only HTTP(S), retries/timeouts are bounded, CORS/binding are local,
exports accept no path, and settings mutate allowlisted DB keys only.

## UI System Compliance

`components.json` is shadcn `base-nova`, CSS variables and RTL enabled. No MUI, Ant, Chakra,
Mantine, Bootstrap, DaisyUI, Flowbite, PrimeReact, or other component framework is installed or
imported. Lucide supplies icons. Recharts primitives are always rendered inside the shadcn
`ChartContainer`/tooltip composition.

## Database Integrity

After the final reset and FTS lifecycle testing, `integrity_check=ok`, `foreign_key_check` is empty,
content=0, and FTS=0. Insert/update/delete/rebuild all matched expectations. Earlier live sessions
proved persisted content and FTS row counts remained equal. History clearing retains bookmarked
content and note while nulling its discovery session.

## Exports

Tests and live output verify versioned JSON, UTF-8 Arabic, nullable metrics, commas/quotes/newlines,
provenance fields, and CSV BOM. Cells beginning `=`, `+`, `-`, or `@` are prefixed with an
apostrophe to prevent spreadsheet formula execution. Export responses never write an arbitrary path.

## Performance

Internal engine, final run: median 78.26 ms, P95 81.98 ms for three concurrent 50 ms fixture
connectors; phases were collection 50.88, persistence 8.98, dedup 4.79, ranking 6.21, clustering
2.18 ms.

| Records | Normalize ms | Rank ms | Dedup ms | Cluster ms |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 0.32 | 3.74 | 93.43 | 4.59 |
| 200 | 0.64 | 6.53 | 378.33 | 7.82 |
| 1,000 | 3.26 | 34.63 | not run beyond product cap | not run beyond product cap |
| 5,000 | 17.14 | 169.00 | not run beyond product cap | not run beyond product cap |
| 10,000 | 33.83 | 348.66 | not run beyond product cap | not run beyond product cap |

Live performance is separate: the final mixed public-source API search was 1,458 ms; GitHub
1,004.06 ms, RSS 367.17 ms, Bluesky 263.41 ms, Hacker News 1,364.17 ms. Deterministic mixed-source
instrumentation recorded the first healthy source at 32.52 ms, medium at 92.70 ms, slow failure at
182.92 ms, and the partial API result at 197.85 ms. The current REST architecture does not stream;
it returns healthy results after all bounded tasks complete. Backend VmRSS varied 4,256 KiB across
31 repeated/large-result observations. Browser post-GC heap decreased from 24,179,612 to 23,037,608
bytes after 20 locale switches, overlay cycles, and navigation. These are bounded observations, not
a formal leak proof.

## Fresh Installation

A source-only copy at `/tmp/mirsad-fresh-verification-20260809` excluded `.venv`,
`node_modules`, build output, Git metadata, and runtime databases. Fresh
`npm run install:all`, `npm test` (82 backend/10 frontend), `npm run build`, and
`npm run doctor` passed after the installer was corrected to create ignored `data` and
`reports` directories.

## Docker

`docker compose config --quiet` passes. Both images built; frontend context is 4.28 kB and API
context 4.62 kB. API and production Vite preview returned HTTP 200 on localhost-only mappings. The
`mirsad_mirsad-data` named volume exists, and saved search `docker-persistence-probe` retained
the same ID/configuration across `docker compose restart`. Compose shut down cleanly without
deleting the volume.

## Test Suite

- Backend: 87 passed in 3.63 seconds; 0 skipped, 0 xfail, no reported warnings.
- Frontend: 12 passed across 5 files in 5.00 seconds; 0 skipped.
- Playwright deterministic: 11 passed, 1 skipped in 1.3 minutes. The skip is the explicit opt-in
  live persisted-session test.
- Live supplemental: source verification and live connector verification exited zero; the final
  public API/search/diagnostics/JSON/CSV workflow exited zero.
- Lint: Ruff and oxlint PASS. TypeScript PASS. Production build PASS.
- Browser console: no application `console.error`, uncaught exception, unhandled rejection, React
  warning, or missing translation warning. The only harness warning is Node reporting that
  `NO_COLOR` is overridden by `FORCE_COLOR`.
- The bounded browser stress snapshot reported no console errors and decreasing post-GC heap/nodes.

## External Blockers

- X, Threads, Telegram, Reddit, YouTube, Mastodon, Instagram, and TikTok lack legitimate configured
  access in this environment.
- Bluesky AppView returns HTTP 403 from this environment.
- TikTok requires approved Research access; Facebook and LinkedIn do not expose unrestricted global
  public-post search through the configured model.
- Fewer than three social connectors are live, so `Social Pilot Ready` is not certified.

## Remaining Internal Problems

- The independent dense holdout demonstrates a deterministic retrieval boundary: semantically
  different records containing the same exact name/phrase saturate lexical relevance and are then
  ordered by supporting signals. No opaque or query-specific tuning was introduced to hide it.
- Memory evidence is bounded backend/browser observation, not a formal retained-heap or long-duration
  leak proof. No monotonic growth was observed in the exercised workloads.
- The source snapshot contains no Git history, so revision/dirty-state provenance remains unprovable.

## Final Requirement Counts

| Status | Count |
| --- | ---: |
| PASS | 85 |
| PARTIAL | 1 |
| FAIL | 0 |
| NOT_APPLICABLE | 0 |
| NOT_PROVEN | 1 |
| BLOCKED_EXTERNAL | 1 |

No Critical or High internal issue remains. The one PARTIAL item is the explicitly bounded memory
evidence scope, not an observed functional defect. Revision traceability is NOT_PROVEN because this
is a source snapshot, and three-social-source verification remains BLOCKED_EXTERNAL. Neither is
converted into a fabricated PASS.

INTERNAL VERIFICATION COMPLETE — READY FOR LIVE SOCIAL CREDENTIAL PILOT
