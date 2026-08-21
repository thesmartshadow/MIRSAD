# MIRSAD Final Requirement Verification - Phase A Baseline

Generated 2026-08-09 (Asia/Baghdad). This is the read-only audit baseline captured before production fixes. Existing reports were not accepted as proof.

## Repository Baseline

- `git status`, `git diff --stat`, `git diff`, and `git log -1` all returned `fatal: not a git repository`. The `.git` path is an empty directory, so revision, tracked changes, and ignored-secret behavior cannot be independently established.
- Version metadata is consistent: root and web packages use `1.0.0-rc1`, Python uses PEP 440 `1.0.0rc1`, and runtime configuration/sidebar use `1.0.0-rc1`.
- Fresh baseline commands: backend `72 passed`; frontend `9 passed`; Playwright `5 passed, 1 skipped`; lint PASS; TypeScript PASS; production build PASS.
- `npm run doctor` passed every required check and warned that `.env` is absent. `npm run verify-sources` exited zero, exposed no secrets, and reported optional source states rather than treating them as local failures.
- Current databases: `data/mirsad.db` and `data/e2e.db` both returned `PRAGMA integrity_check=ok` and no foreign-key violations. The E2E database contained 15 content and 15 FTS rows.

## Requirement Traceability

| ID | Requirement | Code evidence | Test evidence | Fresh runtime evidence | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | Repository revision and dirty state known | `.git/` exists but contains no Git metadata | None | All four required Git commands failed | NOT_PROVEN | No revision or diff baseline can be certified. |
| R02 | v1.0.0-rc1 metadata consistency | `package.json`, `apps/web/package.json`, `pyproject.toml`, `config.py:Settings.version` | Build/import exercise metadata | Values inspected directly | PASS | Python's `1.0.0rc1` is equivalent PEP 440 syntax. |
| R03 | Monorepo and backend domain separation | `apps/web`; `apps/api/mirsad_api/{connectors,domains,services,routers}` | Full suite imports all domains | Source tree inspected | PASS | `services/search.py` is large but remains orchestration rather than a single-file backend. |
| R04 | shadcn/ui-only component system | `apps/web/components.json`; `src/components/ui`; `package.json` | Frontend and E2E suites | Dependency/import scan found no prohibited framework | PASS | Recharts appears only through the shadcn Chart wrapper; icons are Lucide. |
| R05 | No required external LLM | Ranking/dedup/clustering domains contain deterministic code | Ranking, dedup, quality tests | Repository-wide runtime-symbol scan | PASS | Documentation mentions LLM only to state that it is not used. |
| R06 | Registered connector inventory | `services/registry.py:build_connector_registry()` | `test_connectors.py`, `test_social_connectors.py` | Registry built by doctor/verify-sources | PASS | 15 real/restricted connectors registered; mock is explicit opt-in only. |
| R07 | Capability metadata and source taxonomy | `connectors/base.py:ConnectorCapabilities`; per-connector metadata | Social connector/API tests | `/sources` exercised by E2E | PASS | Social, news, and developer/community categories are backend-driven. |
| R08 | Capability honesty | Instagram/TikTok/restricted/Mastodon/Telegram/X metadata | Social connector tests | Source verification output inspected | PASS | No global Instagram/Facebook/LinkedIn claim; Telegram and Mastodon coverage is scoped. |
| R09 | Secrets remain backend-only | `config.py`; registry; non-secret `SourceStatus` schema | config/source API tests | `.env.example`, source JSON, frontend source/bundle scan | PASS | No token values or credential fields were found in production frontend code/output. |
| R10 | Source status semantics are distinct | `services/search.py:_health_state`; `StatusBadge` | Failure acceptance tests | Sources/search UI exercised | PARTIAL | Backend distinctions exist, but some raw status/details remain untranslated and invalid credentials are not in the localized badge map. |
| R11 | RSS fetched/valid/matching stages are correct | `connectors/rss.py:search()` | `test_rss_reports_each_filter_stage_and_strips_html` | BBC feed: `Hormuz` fetched 30/valid 30/matched 1; `العراق` fetched 30/valid 30/matched 0 | PASS | The earlier 90/90/0 condition was query exclusion, not parser/normalizer failure. |
| R12 | GDELT total interactive budget/circuit breaker | `connectors/gdelt.py:search()`; `config.py` budget settings | `test_gdelt_total_budget_and_timeout_circuit_breaker_are_bounded` | 3001.09 ms/2 attempts; 3001.52 ms/2; next call 0.02 ms/circuit open | PASS | Did not regress to the old approximately 18.9-second behavior. |
| R13 | Independent connectors execute concurrently | `SearchService.execute():asyncio.gather` | `test_connector_failure_is_isolated_and_audited`; benchmark fixtures | Three 50 ms fixtures completed in median 75.31 ms total | PASS | Runtime is bounded by the slowest connector plus processing, not their sum. |
| R14 | Stale request protection, including navigation | `search-page.tsx:runSearch()` generation guard | No route-away regression test | Code path inspected; Search A/B generation is guarded | FAIL | Unmount/navigation does not abort or invalidate `runSearch`; late completion can update global state and navigate back. |
| R15 | Unified nullable content model | `ConnectorItem`; `ContentItem`; `ContentMetric`; API/TS types | Social normalization tests | Normalized fixtures inspected | PASS | Missing raw social metrics remain absent and nullable metric columns remain null. |
| R16 | UTC/timezone correctness end to end | ORM `DateTime(timezone=True)` columns | No offset persistence regression test | SQLite reload returned naive datetimes; API JSON omitted `Z`/offset | FAIL | Browser interprets stored UTC as local wall time; mixed aware/new and naive/existing records can raise `TypeError`. |
| R17 | Deterministic query intent processing | `domains/query.py:process_query()` | query/ranking tests | Direct keyword/phrase/hashtag/handle/URL/Arabic probes | PASS | Variants are conservative and diagnosed. |
| R18 | Conservative Arabic normalization | `normalize_arabic`, `normalize_text` | positive and adversarial query tests | Direct normalization inspected | PASS | Diacritics/tatweel/Alef/digits/format controls are bounded; no broad synonym expansion. |
| R19 | FTS5/BM25 supports normalized Arabic | `database.py:create_fts_index`; `SearchService._bm25_scores` | Only Latin FTS CRUD coverage | Indexed `وزارة الصحة`; normalized query `وزاره الصحه` matched 0 while raw matched 1 | FAIL | Python matching succeeds, but the Arabic BM25 component silently disappears for normalized forms. |
| R20 | Candidate retrieval preserves strongest candidates | `SearchService.execute()` round-robin truncation before scoring | No candidate-boundary regression test | Limit 2 fixture dropped the strongest exact-title item behind weak items | FAIL | Connector arrival/source ordering can cause silent recall loss before ranking. |
| R21 | Local language filtering is correct | `SearchService.execute()` eligibility; `_persist_item()` detection | No unknown-language filter test | Arabic filter admitted English `language=und`; GitHub programming language is used as content language | FAIL | Detection happens after filtering; GitHub/GDELT language formats are incompatible with generic filters. |
| R22 | Local time range is authoritative | `_since()` and connector hints | No old-record rejection test | 400-day-old fixture was accepted by a `24h` search | FAIL | Connector `since` is only a hint; the common pipeline does not enforce known publication time. |
| R23 | Candidate retrieval and final ranking remain distinct | matching in `domains/ranking.py`; scoring after persistence | ranking/search-service tests | Pipeline inspected | PARTIAL | Conceptual stages exist, but pre-ranking round-robin truncation mixes source fairness with candidate quality. |
| R24 | Authoritative explainable scoring formula | `calculate_score()` | `test_ranking.py` | Independent component calculation matched output | PASS | Supporting signals are relevance-gated before penalty and clamp. |
| R25 | Relevance beats popularity/freshness/presence | `calculate_score()` relevance-squared support factor | ranking signal regressions | Relevant old/quiet=45.00; weak collision fresh/viral/multi-source=23.54 | PASS | Cross-source and engagement cannot independently rescue weak relevance. |
| R26 | Score component distributions are informative | `quality.py:_component_statistics()` | quality fixture test | Fresh statistics recalculated | PARTIAL | Relevance saturates near 100; fixture source confidence=70, cross-source=0, novelty=100 are dead signals in this evaluation. |
| R27 | Published search quality metrics are mathematically correct | `quality.py:_evaluate_cases()` | `test_search_quality_fixture_suite_is_reproducible` | Independent raw judgment recalculation | FAIL | Reported `Precision@K` divides by returned-set size. Standard primary P@5/P@10 are 0.25/0.125, not 1.0/1.0. |
| R28 | Evaluation is independent and difficult enough | Primary/hard fixtures in `quality.py` | quality suite | Corpus/judgments inspected | PARTIAL | Primary candidate pools average 1.25; hard set overlaps primary concepts and was used during tuning. |
| R29 | Arabic/English/mixed quality reported separately | `quality.py:_language_metrics()` | quality test covers representative queries | Recalculated from judgments | PARTIAL | Returned-set metrics are present by language, but standard P@K and independent language difficulty are not. |
| R30 | Deterministic ordering | `_sort_items()` stable score/time/source/external tie breaker | clustering order and connector isolation tests | Repeated fixture ordering inspected | PASS | Logical identical inputs have explicit stable tie-breakers. |
| R31 | Platform-specific engagement calibration | `domains/engagement.py:PLATFORM_SCALES` | engagement/social connector tests | 0,1,10,100,1k,10k,1m probes | PASS | Values are finite/monotonic; saturation is explicit per-platform. Missing and zero remain distinguishable in raw/nullable fields. |
| R32 | Freshness monotonic half-life decay | `ranking.py:freshness_score()` | freshness tests | 10m through 1y values recalculated | PASS | 48-hour half-life is monotonic, bounded, and documented. |
| R33 | Multi-stage deduplication | `domains/deduplication.py` | `test_multi_stage...`, transitive false-merge test | URL/fingerprint/near-duplicate adversarial probe | PASS | Originals remain persisted and broad related items did not merge. |
| R34 | Duplicate and cluster semantics remain coherent | `find_duplicate_groups`; `cluster_items` | separate dedup/cluster tests | Same canonical URL with different excerpts deduped but entered separate clusters | PARTIAL | Duplicate and cluster concepts are separate, but a proven duplicate relationship can be split across clusters. |
| R35 | Story clustering is deterministic and not broad-topic grouping | `cluster_items()` | stable completion-order test | Same-event/different-event adversarial probe | PARTIAL | Basic behavior is acceptable; evaluation incorrectly judges cluster pairs against duplicate pairs and does not validate story-level ground truth. |
| R36 | Cross-source presence counts independent platforms | duplicate group unique `sources`; `cross_source_score` | dedup/social analytics tests | 20 same-platform semantics inspected | PASS | Repeated records from one source contribute one source. |
| R37 | Social Reach is deterministic and non-truth metric | `engagement.py:social_reach()` | social analytics tests | Formula and UI wording inspected | PASS | Separate from Final Score and returns null for non-social sources. |
| R38 | Trend buckets/baseline are correct | `analytics.py:time_buckets`, `trend_indicator` | 7-day/all-time tests | Four known 15-minute buckets manually recomputed | PASS | Chronology retained; baseline zero handled descriptively without significance claim. |
| R39 | Stored analytics use real session data | `SearchService` analytics payload; `build_analytics()` | social analytics and acceptance tests | Snapshot pipeline inspected | PASS | No production placeholder chart data found. |
| R40 | Related-term extraction handles Arabic/English noise | `analytics.py` stopwords/URL/query exclusion | analytics tests | Implementation inspected | PASS | Per-document repeated terms, URLs, stopwords, and original query tokens are excluded. |
| R41 | One authoritative locale/direction state | `I18nProvider`; `DirectedApplication` | locale component/E2E tests | DOM EN/AR switches in Playwright | PASS | Locale drives html lang/dir and DirectionProvider; early HTML script handles cold start. |
| R42 | Immediate EN/AR switching | same as R41 | E2E locale test | 20 Search-route switches passed | PASS | No reload required. |
| R43 | Twenty-switch stress across major routes | `I18nProvider` | one Search-route 20-switch E2E | Existing test passed | PARTIAL | Analytics/Settings/loaded Results and narrow multi-route stress are not covered. |
| R44 | Language switch preserves active user work | provider boundaries; SearchStateProvider | query/sidebar E2E assertion | Query/sidebar retained | PARTIAL | Loaded results, filters, sort, open sheets/clusters, and bookmark notes are not proven. |
| R45 | Portal direction and keyboard behavior | root DirectionProvider; Base UI portal primitives | general E2E interaction | Dialog/Sheet basic flows passed | PARTIAL | Dropdown/Select/Popover/Tooltip/Command EN-AR-EN focus/alignment matrix is not independently exercised. |
| R46 | Sidebar direction desktop/mobile | `ApplicationSidebar`; `Sidebar` mobile Sheet | locale E2E | Desktop side/collapse and narrow rendering passed | PARTIAL | Mobile sheet open/collapse persistence under repeated language switching is not proven. |
| R47 | Mixed bidi external content isolation | result/bookmark components use `dir="auto"`; technical strings LTR | live-session E2E optional | Fixture/live-result DOM inspected where available | PASS | Retrieved text is not forced to page direction. |
| R48 | Localization completeness | `lib/i18n.tsx` | localization tests | production JSX literal scan | PARTIAL | Metric keys, duplicate match stages, source status strings, and backend warning/detail text can remain English in Arabic UI. |
| R49 | Cold-start locale without harmful flash | inline `apps/web/index.html` locale script | persisted-Arabic E2E | Arabic cold start passed | PASS | Direction is set before the module application renders. |
| R50 | Accessibility of critical UI | labels/shadcn focus primitives | Axe Search/Sources/Settings E2E | Three English routes passed serious/critical scan | PARTIAL | Arabic, overlays, all routes, and narrow keyboard traversal are not comprehensively proven. |
| R51 | Frontend state ownership has no conflict | locale/theme providers; SearchState; form-local state | frontend/E2E tests | Provider graph inspected | PASS | No duplicate direction state; current search is global and form editing is local by design. |
| R52 | API/Pydantic/TypeScript contract alignment | `schemas.py`; `types/api.ts`; `read_models.py` | API tests | Representative JSON inspected | PARTIAL | Fields/enums/nullability align, but persisted timestamps violate the timezone semantics expected by both clients. |
| R53 | Database integrity and FTS CRUD sync | schema, triggers, `data_management.py` | `test_content_insert_populates_fts_index` | both DB integrity/FK checks passed | PASS | Insert/update/delete and rebuild are covered. |
| R54 | Search-history/bookmark lifecycle safety | `clear_history()` nulls bookmark session before history deletion | operational/acceptance tests | Code/DB constraints inspected | PASS | History clearing preserves bookmarked content reference and note. |
| R55 | CSV/JSON exports are accurate and safe | `services/exporting.py` | `test_csv_is_utf8_with_bom_and_prevents_spreadsheet_formulas`; API export tests | UTF-8 BOM/formula behavior inspected | PASS | Export is returned, never written to a user path; nullable metrics are preserved in JSON. |
| R56 | Saved search CRUD/rerun/persistence | records router/service; `SavedSearch` | acceptance/API/E2E workflows | create/run UI passed | PASS | Stores complete SearchRequest; it is not a monitor. |
| R57 | Bookmark CRUD/note/persistence | records router/service; `Bookmark` | acceptance/API/E2E workflows | bookmark/note UI passed | PASS | Original content is not edited. |
| R58 | Search diagnostics definitions and instrumentation | session diagnostics; connector run model | operational/reliability tests | RSS labels inspected | FAIL | Multi-request connectors reset diagnostics per HTTP call; `verify_connectors.py` also aliases fetched count as returned count. |
| R59 | Internal and live performance are separated | benchmark and live verification scripts | benchmark fixture | Internal report and fresh live connector telemetry inspected separately | PASS | Fixture time is explicitly not labeled network time. |
| R60 | Algorithmic scaling is measured and bounded | benchmark script; max result limit 200 | benchmark execution | 100/200 dedup 84.42/365.91 ms; ranking 10k 325.35 ms | PASS | Quadratic dedup is bounded to 200 interactive candidates. |
| R61 | Memory/resource sanity | Bounded limits and pagination | No resource-specific test | No formal or repeated-process memory measurement | NOT_PROVEN | No leak claim is made. |
| R62 | Pagination preserves session ranking | API returns ranked session; frontend slices results | frontend workflow tests | Code path inspected | PASS | Pagination does not rerank or refetch pages. |
| R63 | Connector error isolation/classification | `BaseConnector`, `SearchService._run_connector` | 401/403/429/500/timeout/malformed failure tests | partial search tests passed | PASS | Healthy source records survive failed peers without stack leakage. |
| R64 | Multi-request connector telemetry is complete | `BaseConnector.request_json()` resets diagnostics | pagination connector tests do not assert aggregate attempts | X two-page probe reported one attempt | FAIL | Token/search, pagination, and search/statistics connectors lose earlier request telemetry. |
| R65 | `verify-sources` is safe and actionable | `scripts/verify_sources.py` | source-verification tests | Fresh command exited 0; states/latency shown; no secrets | PASS | Optional unconfigured/external failures do not become local application failure. |
| R66 | `doctor` checks real prerequisites | `scripts/doctor.mjs` executes version/import/FTS/DB/registry checks | N/A | Fresh command passed with `.env` WARN | PASS | It does not simply print fixed PASS values. |
| R67 | Startup/stop scripts work from stopped state | `start.sh`; `stop.sh` | No script test | Not freshly executed during Phase A | NOT_PROVEN | Code has strict Vite port/PID checks; graceful termination still requires runtime proof. |
| R68 | Optional Docker builds and runs | `docker-compose.yml`, Dockerfiles | No container E2E | Compose inspected only | NOT_PROVEN | Runtime build/reachability/volume persistence remains unproven. |
| R69 | Fresh installation works from isolated copy | `scripts/install.sh`; README | None | Not yet executed | NOT_PROVEN | Existing `.venv` and node_modules cannot serve as fresh-install proof. |
| R70 | Production build | Vite/TS configuration | build compiles app/tests separately | Fresh `npm run build` passed, 2768 modules | PASS | Largest chunks: chart 347.16 kB, main 305.79 kB. |
| R71 | Test-suite integrity/counts | pytest/vitest/Playwright config | 72 backend; 9 frontend; 6 E2E discovered | Fresh suites executed | PARTIAL | One live E2E is intentionally skipped; important stale-route/timezone/language/time/telemetry cases were absent. |
| R72 | Every UI route loads without console errors | App route table | existing workflows cover most routes | No full EN/AR desktop/narrow route crawl yet | NOT_PROVEN | Existing E2E console monitor is valuable but not a complete crawl. |
| R73 | No fake production data | mock flag defaults false; mock registry conditional | config/E2E fixture mode tests | registry and production source paths inspected | PASS | Mock cannot silently replace a live failure. |
| R74 | End-to-end real-data provenance | connector normalization/read model/export pipeline | fixture connector and export tests | Live HN/GitHub normalization verified, but no fresh browser/export trace | PARTIAL | Full external-response through frontend/export chain is not independently proven in this environment yet. |
| R75 | External link/content safety | `safeExternalUrl`; text rendering; `rel=noopener noreferrer` | frontend tests | source scan found no retrieved-content HTML injection | PASS | Chart's static CSS `dangerouslySetInnerHTML` is not external content. |
| R76 | Server-side fetch targets are controlled | connector fixed metadata; RSS from server config only | connector host/error tests | API/config path inspected | PARTIAL | Normal users cannot set URLs, but `startswith` host validation is weaker than exact origin validation. |
| R77 | Settings schema is authoritative | settings router validators | operational settings tests | Boolean ranking vector summing to 1.0 was accepted | FAIL | Python bool is an int; ranking validation does not reject booleans. |
| R78 | Audit events are meaningful and secret-free | search/settings/data audit writes | `test_connector_failure_is_isolated_and_audited` and operational tests | event contexts inspected | PASS | Events contain source/session/category, not headers or credentials. |
| R79 | Documentation matches implementation | README/docs | N/A | Code/document comparison | PARTIAL | Docs overstate pre-insert time/language constraints and search-quality report naming; search query table claims fields not persisted there. |
| R80 | Credential documentation matches code | `docs/social-credentials.md`; config/registry/connectors | config/source tests | Variable-by-variable comparison | PASS | Required/optional fields and implemented refresh behavior align with current code. |
| R81 | Live social collection readiness | credential-requiring connectors and Bluesky public adapter | deterministic adapters pass | No social credentials; Bluesky HTTP 403 | BLOCKED_EXTERNAL | Engineering adapters exist, but three real social sources cannot be verified without legitimate credentials/access. |
| R82 | Live supplemental sources | HN/GitHub/RSS/GDELT connectors | deterministic connector tests | HN 10 results/1936 ms; GitHub 11/1249 ms; RSS works; GDELT bounded timeout | PASS | Live availability is supplemental and current-environment-specific. |
| R83 | GitHub repository/issues/PR scopes | `GitHubConnector` and registry scope config | issue/PR normalization and partial-scope tests | anonymous repository live probe passed | PASS | Source-code search is not enabled. |
| R84 | Social analytics/platform presence | analytics builder and cluster persistence | social analytics tests | production pipeline inspected | PASS | Values are derived only from stored session items. |
| R85 | Security headers, local CORS, local binding, request limits | `main.py`; config; scripts | API security/validation tests | response/config/source inspection | PASS | Generic 500 response avoids frontend stack traces. |
| R86 | Search request validation | `schemas.py:SearchRequest` | API/query tests | blank/oversized/bounded fields inspected | PASS | 300-character query and 200-result limits are authoritative. |
| R87 | Print-friendly institutional report | report route/page and stored analytics | E2E print report test | Report rendered from stored fixture data | PASS | Browser Print/Save as PDF is used; no heavyweight PDF dependency. |
| R88 | Per-source progress and partial failure UX | Search page pending/warning/status UI | E2E partial behavior | UI code/workflow inspected | PARTIAL | It shows all sources pending then final states, but no true incremental completion arrives before the full response. |

## Issues Found Before Fixes

### High

1. SQLite discards timezone offsets, API JSON emits naive timestamps, and repeated searches can compare naive persisted values with aware connector values and crash.
2. Language filtering occurs before unknown-language detection; `und` bypasses requested language, GitHub programming language is misused as content language, and common GDELT names/codes are not normalized.
3. Known old records are not locally rejected for selected time windows.
4. Pre-ranking round-robin truncation can discard the strongest candidate based on source/result order.
5. Arabic-normalized queries cannot receive BM25 evidence against raw Arabic FTS content.
6. Search quality labels claim Precision@K while calculating precision over the available returned set.
7. Search completion after route unmount can overwrite global state and navigate the user back.

### Medium

1. HTTP diagnostics reset per request, under-reporting pagination/token/statistics work.
2. Same-URL duplicates can be split into different story clusters.
3. Ranking settings accept boolean weights.
4. Localization is incomplete for raw metrics, match stages, source states, and backend details.
5. Evaluation fixtures do not exercise cross-source/novelty/source-confidence distributions and the cluster judgment is actually duplicate-pair judgment.
6. Documentation contains concrete pipeline and data-model inaccuracies.

### Low

1. Host allowlisting uses string prefixes rather than parsed exact origins, although current URLs are connector-built rather than user-controlled.
2. `components.json` declares `rtl: false` even though the runtime uses a shared DirectionProvider; no observed runtime failure is attributable to it.

### External Blocker

- No valid X, Threads, Telegram, Reddit, YouTube, Mastodon, Instagram, or TikTok credentials are configured, and Bluesky returns HTTP 403 from this environment. Three live social connectors therefore cannot be proven.

## Phase A Counts

The counts below are for the 88 matrix requirements above and will be recalculated after fixes and full revalidation.

<!-- phase-a-counts: generated from the matrix status column -->

| Status | Count |
| --- | ---: |
| PASS | 52 |
| PARTIAL | 19 |
| FAIL | 10 |
| NOT_APPLICABLE | 0 |
| NOT_PROVEN | 6 |
| BLOCKED_EXTERNAL | 1 |

## Phase B/C Final State

All ten original FAIL rows were reproduced, fixed, and revalidated. The authoritative post-fix
matrix and evidence are in `reports/final-independent-verification.md`.

| Status | Count |
| --- | ---: |
| PASS | 85 |
| PARTIAL | 1 |
| FAIL | 0 |
| NOT_APPLICABLE | 0 |
| NOT_PROVEN | 1 |
| BLOCKED_EXTERNAL | 1 |

The baseline above is intentionally retained as the before-fix audit rather than rewritten to look
successful after the fact.
