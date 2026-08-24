# MIRSAD v1.2 Retrieval Intelligence and Coverage

## Executive assessment

MIRSAD v1.2.0 adds evidence-bound retrieval intelligence without changing the authoritative Phase 2 route or final scoring. Local SQLite/FTS5 memory is now an explicit bounded acquisition lane; all-time searches retain historical local appearances; entity aliases require two independent evidence sources and cannot be created from embeddings; and every persisted session has a typed Coverage Report separating search outcome, acquisition lanes, source participation, health, and gaps.

The adaptive router remains **SHADOW ONLY**. Deterministic replay modeled 17 fewer requests out of 98 (17.35%) with recall 1.0 and no labeled evidence loss, but handle, hashtag, person, historical, exact-phrase, English-topic, and recent classes each have only one independent case. That is insufficient for production promotion. No shadow recommendation influenced a live search.

The operator database remained intact. The live validation appended legitimate content/session/appearance/cluster/learning rows but retained both bookmarks and the saved search. Final SQLite integrity, foreign keys, and FTS parity are clean.

## Protected baseline

| Item | Before |
| --- | --- |
| Branch | `v1.2-intelligence` |
| HEAD | `33793d6a00823bfe35ac18485a9b358c3d588880` |
| Operator database | `data/mirsad.db` |
| Size / SHA-256 | 11,714,560 bytes / `1f9a8329b0a958064628c0adaeba6959b2663fe73a9c0a60ea38e2439661724f` |
| SQLite | `integrity_check=ok`; FK violations 0 |
| Content / FTS | 843 / 843 |
| Sessions / appearances | 47 / 1,285 |
| Bookmarks / saved searches | 2 / 1 |
| Clusters | 1,046 |
| Utility / shadow observations | 599 / 180 |
| Alias edges | 0 |

A SQLite-consistent backup was created outside `data/` at `/tmp/mirsad-v12-operator-20260821T133000Z.db`; SHA-256 is `7026fbc7e3e1fe1a4866c3a61c823e4a80a54a4c00393b6e77c0fa468cff6b21`, and its integrity check passed. Tests and deterministic evaluations used isolated databases. No reset path was invoked against operator state.

## Research and architecture decision

Primary technical research is recorded in `reports/mirsad-v1.2-research-sources.md`. It covers SQLite FTS5/query planning, YouTube, GitHub, Bluesky AppView, Mastodon, GDELT, Common Crawl, and the optional disabled SearXNG architecture. The resulting constraints are reflected directly in the implementation: indexed bounded local narrowing, fixed connector capabilities/hosts, current health separated from utility, no unsupported global-search promise, and no arbitrary crawling.

All visual research used only the 14-source whitelist. The full accept/reject matrix and component traceability are in `reports/v1.2-ui-source-research.md`. No AI-generated asset, template, outside UI reference, fake source, or fake analytical record was used. Runtime selection remains React/shadcn/Tailwind, GSAP, authored SVG, and the existing single lazy Three.js renderer. Every proposed additional creative runtime was rejected because it duplicated ownership or added no analytical meaning.

## Deterministic retrieval baseline

`reports/v1.2-retrieval-baseline.json` is a hash-addressed 14-query replay covering Arabic/English topic, entity, person, mixed language, handle, hashtag, CVE/GHSA, exact phrase, recent, and historical intent.

| Metric | Baseline |
| --- | ---: |
| Queries | 14 |
| Production requests | 98 |
| Zero-yield requests | 38 |
| Useful candidates | 87 |
| Mean labeled recall | 1.0 |
| Useful evidence per request | 0.693878 |
| Mean time to useful evidence | 377.5 ms |

This replay evaluates retrieval, not the frozen ranker. Labels were fixed in `apps/api/tests/fixtures/v12_retrieval_intelligence.json`; the evaluation did not tune against an unseen production holdout.

## Adaptive retrieval router

The v1.1 Phase 3 shadow mechanism was refined rather than replaced. Each shadow decision now records long-term utility, query/source compatibility, current availability, expected gain, expected cost, selection/defer status, and concise reasons. Temporary timeout/403/rate-limit state is evaluated as current availability and never written as negative long-term semantic utility.

| Replay result | Production | Shadow |
| --- | ---: | ---: |
| Requests | 98 | 81 |
| Modeled requests saved | - | 17 |
| Request reduction | - | 17.3469% |
| Mean recall | 1.0 | 1.0 |
| Labeled evidence lost | 0 | 0 |
| Aggregate estimated latency avoided | - | 4,400 ms |

Per-class minimum shadow recall was 1.0 for every represented class. The promotion gate nevertheless failed its independent-sample requirement. Completion-order invariance remains a mandatory gate and passed independently. Decision: **ADAPTIVE ROUTER REMAINS SHADOW**. Production Phase 2 planning and execution are unchanged.

## Entity and alias intelligence

`EntityAliasEdge` stores left/right values, normalized labels, relationship type, bounded structured evidence, source identities, support count, confidence, status, created time, and last observation. A relation becomes retrievable only when confidence is at least 0.8, status is `supported`, and at least two independent sources support it. Evidence history is bounded to 20 entries per edge.

The query lattice records `ENTITY_ALIAS` as a child of the original variant with confidence, drift risk, source origin, and reason. Automatic alias drift is limited to 0.2; identifiers never receive alias expansion. Embedding similarity cannot create or merge an alias.

Deterministic evaluation admits `وزارة التخطيط` to `Ministry of Planning` only after two independent evidence sources, rejects single-source `علي` to `Ali` as collision-prone, and adds no unsupported alias for `علي فراس`. Common Arabic single names are explicitly protected. The operator database contains zero alias edges after live validation, which is the correct outcome: no live evidence met the promotion requirements.

## First-class local and historical retrieval

Local memory is a deliberate round-zero acquisition lane. It uses exact indexed lookup for identifiers/handles/hashtags and bounded FTS5 retrieval before any semantic opportunity; it does not scan the corpus semantically. Limits are clamped, query strings remain parameterized, and local rows carry `acquisition_path=LOCAL_MEMORY` with zero network requests.

All-time/historical intent records a distinct historical local lane. Current live collection can still participate, but local historical evidence is not erased. Canonical identity prevents a local and live appearance from becoming two final records; appearance provenance remains separate.

The deterministic memory evaluation found local useful evidence for 12 of 14 queries (17 useful candidates) and historical evidence for one query (2 useful candidates). In the bounded live matrix, local retrieval averaged 4.27 ms and contributed 95 of 131 final appearances across nine sessions; the historical lane contributed two final appearances in the all-time case.

Timestamp semantics are explicit:

- `published_at` is source publication time or null.
- `first_seen_at` is MIRSAD's first observation and is immutable after insertion.
- `last_seen_at` advances when MIRSAD observes the canonical item again.
- `retrieved_at` is the latest non-local retrieval execution.

Publication time is never inferred from ingestion time. Existing rows were additively backfilled for observation timestamps only.

## Coverage intelligence

Coverage is persisted with each SearchSession and returned both in the session read model and by `GET /api/v1/searches/{session_id}/coverage`. It is not recomputed from frontend state. The model has independent outcome and coverage states, source rows, LIVE/LOCAL_MEMORY/HISTORICAL lane summaries, represented final platforms, web-discovery state, typed gaps, stop enum, and human stop explanation. No fake coverage percentage is calculated.

Gap reasons are `NOT_SELECTED`, `NO_CAPABILITY`, `UNCONFIGURED`, `RESTRICTED`, `WEB_DISCOVERY_DISABLED`, `EXTERNAL_LIMIT`, `UNAVAILABLE`, `FAILED`, `TIMEOUT`, `RATE_LIMITED`, `CIRCUIT_OPEN`, `NO_MATCHES`, `NO_MATCHES_IN_TIME_RANGE`, and `NOT_APPLICABLE`.

A post-fix persisted validation session (`6018146c-e40b-47f2-9ae3-659082847b58`) proves the critical truthfulness case. Bluesky was unselected and externally limited, executed no live request, yet contributed six final Bluesky records through local memory. Its source row remains `selected=false`, `executed=false`, `requests=0`, `status=EXTERNAL_LIMIT`; the LOCAL_MEMORY lane reports the contribution. GitHub is independently reported as a current external limit. X, Threads, and Reddit are `WEB_DISCOVERY_DISABLED`, not connector failures.

The original live matrix was captured before this current-health read-model defect was corrected, so its historical case objects remain unedited evidence. The report appends the complete post-fix session readback rather than rewriting old observations.

## Why selected and why stopped

Normal coverage exposes concise planner-supported reasons such as capability fit, current availability, and acquisition constraints. Advanced diagnostics retain expected utility and deferred reasons. No claim is made from absent planner evidence.

Stop reasons now include human explanations. For example, `USER_LIMIT` explains that the configured final result limit was met; `SATISFIED` explains that available evidence met the retrieval target; `LOW_MARGINAL_GAIN` explains why another bounded round was not justified. Search outcome and incomplete coverage remain independent.

## UI rebuild

The route-by-route before audit is `reports/v1.2-ui-before-audit.md`; the measured comparison is `reports/v1.2-ui-comparison.md`.

- The shell is a numbered retrieval instrument rather than a default sidebar dashboard.
- Search preserves idle/active/results spatial continuity and adds a first-class Coverage tab.
- Results remain a wide ruled evidence ledger with compact platform/acquisition provenance.
- Analytics uses a numerical signal band instead of generic KPI cards.
- Clusters adds deterministic real-data SVG geometry with an accessible ledger.
- History is a temporal session ledger; Sources is a capability/health topology; System is a ruled engineering console.
- Compare, Saved Searches, Bookmarks, Settings, and report/detail views share the same hierarchy with reduced Card chrome.
- Motion is state-driven through scoped/reverted GSAP. No second motion engine or scroll mediation was added.
- Root-owned RTL, bidi isolation, native scrolling, mobile Sheets, reduced motion, and WebGL fallback are preserved.

The guarded screenshot matrix contains 23 files under `reports/v1.2-ui-screenshots/`: idle light/dark, active, results, coverage overview/gaps/local/historical/source reason, Explain Score, all major routes, Arabic RTL, mobile, reduced motion, and WebGL fallback.

## Rendering and bundle evidence

The production build produced a 305.91 kB / 96.37 kB gzip main chunk, a 67.34 kB / 17.72 kB gzip Search chunk, a 69.96 kB / 27.42 kB gzip GSAP chunk, and a separately lazy 724.23 kB / 184.67 kB gzip Three.js chunk. Essential navigation/search does not wait for Three.js. `?webgl=off` was verified to show the SVG fallback with zero canvases.

The existing renderer remains bounded, uses one visible WebGL system, pauses/settles with state, disposes resources, and cannot block search. Browser stress moved from 28,380,848 to 25,597,952 JS heap bytes and from 4,551 to 2,681 nodes after the route cycle; this is evidence of no monotonic browser resource growth, not a universal memory guarantee.

## Performance

The nine-query v1.2 live matrix averaged:

| Phase | Mean |
| --- | ---: |
| Planning | 10.95 ms |
| Local retrieval | 4.27 ms |
| Live collection | 1,765.85 ms |
| Semantic preparation | 1,276.54 ms |
| Ranking | 213.63 ms |
| Clustering | 80.77 ms |
| Server total | 2,840.44 ms |
| Client wall | 2,885.37 ms |

For the five queries shared with the v1.1.1 evidence, observed mean server total changed from 3,301.8 ms to 2,526.4 ms. This is not claimed as a causal speedup: the live runs had different result limits/cache state and external network conditions. The defensible v1.2 cost is the new bounded local lane at 4.78 ms mean for those matched cases. The v1.1.1 semantic-overlap correctness gate remains intact (exact scores/order, bounded cache, no steady-state RSS growth in its three-repeat benchmark).

No production router latency claim is made because adaptive routing was not executed. Its 4,400 ms aggregate saving is a deterministic replay estimate only. The local lane makes useful persisted candidates available before the network returns, but final ranking still waits for the authoritative candidate set.

SQLite query-plan evidence for literal local lookup uses the new lowercase expression indexes for external IDs and author handles through a `MULTI-INDEX OR`; FTS remains the bounded candidate lane. No BM25 or FTS ranking semantics changed.

## Bounded live matrix

`reports/v1.2-live-matrix.json` contains nine append-only real sessions: `بغداد`, `وزارة التخطيط`, `الذكاء الاصطناعي`, `OpenAI`, `Linux kernel security`, `#بغداد`, `@openai`, `CVE-2026-61371`, and all-time `Iraq 2003 reconstruction`.

- Seven searches returned results; five reached the 20-result limit, the hashtag returned 11, and the historical case returned 20.
- `@openai` and `CVE-2026-61371` legitimately returned zero and remained partial after low marginal gain. No evidence was fabricated.
- GDELT timeout/external state was isolated; healthy/live and local results survived.
- Bluesky current public access returned an external 403 during source verification. Configuration remains distinct from current external availability.
- SearXNG remained disabled. X, Threads, and Reddit were never misreported as direct connector failures.

External network variance is explicitly observational. Providers were not repeatedly hammered.

## Security and data safety

- Connector hosts and existing SSRF/private-address/redirect boundaries are unchanged.
- Local lookup uses SQLAlchemy or bound SQL parameters; no user text is interpolated into SQL.
- Alias values/evidence are bounded stored text and render through React text nodes; no raw HTML path was added.
- Coverage/SSE models expose safe enums/counts/reasons, no exception dump, credential, token, or private URL.
- No arbitrary target fetch, login scraping, CAPTCHA bypass, proxy rotation, browser-session harvesting, or external runtime was introduced.
- A credential-pattern scan over tracked source returned no new frontend or report secret.
- The guarded live E2E requires opt-in, accepts only a `127.0.0.1` origin, requires an existing session ID, and contains no reset action.

## Verification

| Gate | Result |
| --- | --- |
| Backend tests | 227 passed |
| Frontend Vitest | 36 passed in 11 files |
| Isolated Playwright | 11 passed; 7 correctly skipped opt-in live cases |
| Guarded current-code v1.2 Playwright | 1 passed; all routes and screenshot assertions |
| Ruff / Oxlint / TypeScript | Passed |
| Production Vite build | Passed |
| Doctor/startup | Passed at `1.2.0`; SearXNG optional warning only |
| Source verification | Completed: 6 pass, 8 expected warn, 1 Bluesky external HTTP 403; zero internal failures |
| Mixed-source order invariance | Passed for 11 queries with identical final identities/order |
| SQLite / FK / FTS | `ok` / 0 / 900=900 |
| Restart persistence | Version `1.2.0`; history, bookmarks, saved search, content, FTS readable |
| Browser console/page errors | None in guarded matrix |
| Secret scan | No credential-pattern match in tracked source |

## Operator database after validation

| Item | After | Preservation |
| --- | ---: | --- |
| Size / SHA-256 | 14,282,752 bytes / `f58361860ad52398efa14d8425263dac41f9cbc4e8197258452bc3cb061b5934` | Readable |
| SQLite / FK | `ok` / 0 | Passed |
| Content / FTS | 900 / 900 | Parity; +57 legitimate live content |
| Sessions / appearances | 59 / 1,536 | Initial 47 / 1,285 retained |
| Bookmarks / saved searches | 2 / 1 | Exactly preserved |
| Clusters | 1,253 | Initial rows retained; live growth |
| Utility / shadow observations | 779 / 228 | Append-only live growth |
| Alias edges | 0 | No unsupported relation admitted |

The final database is expected to have a different SHA from the baseline because bounded live searches appended evidence. No prior operator row was reset or deleted.

## Files changed

| Files | Reason / behavior | Coverage |
| --- | --- | --- |
| `apps/api/mirsad_api/database.py`, `models.py` | Additive timestamp/alias schema, migrations, local exact indexes | v1.2 backend tests; doctor; SQLite plan/integrity |
| `apps/api/mirsad_api/domains/coverage.py`, `schemas.py` | Typed persisted Coverage Report and gap vocabulary | backend coverage tests; frontend coverage tests |
| `apps/api/mirsad_api/mafer/aliases.py`, `planning.py` | Evidence-bound aliases feed the unchanged existing lattice; historical lane planning | entity/drift/collision tests |
| `apps/api/mirsad_api/mafer/memory.py` | First-class bounded literal/FTS local and historical retrieval | memory/timestamp tests; query-plan evidence |
| `apps/api/mirsad_api/mafer/shadow.py` | Deterministic utility decisions/reasons with health separation; no production effect | router isolation/gate tests; replay report |
| `apps/api/mirsad_api/services/search.py`, `read_models.py` | Persist timestamps/coverage, live-only utility attribution, canonical local/live provenance | search-job provenance/coverage tests; live matrix |
| `apps/api/mirsad_api/routers/search.py` | Session coverage endpoint | API test and guarded Playwright |
| `apps/api/tests/test_search_jobs.py`, `test_v12_retrieval_intelligence.py`, fixture | Regression coverage for provenance, routing, aliases, memory, timestamps, coverage | full pytest |
| `apps/web/src/components/search/coverage-view.tsx`, test, `lib/api.ts`, `types/api.ts`, `lib/i18n.tsx` | Coverage UI/API/types/localization | Vitest and live Playwright |
| `apps/web/src/components/layout/app-layout.tsx`, `shared/page.tsx`, `ui/card.tsx`, `index.css` | New instrument shell, reduced Card chrome, shared route hierarchy, responsive/RTL styles | workflow tests, Playwright, screenshots |
| `apps/web/src/components/analytics/analytics-view.tsx`; pages `analytics`, `bookmarks`, `clusters`, `compare`, `history`, `report`, `saved-searches`, `search`, `settings`, `sources`, `system` | Route-by-route rebuild using existing backend state | workflow tests, accessibility route matrix, guarded screenshots |
| `apps/web/e2e/v12-retrieval-live.spec.ts`, `src/test/workflows.test.tsx` | Guarded all-route/screenshot validation and version behavior | Playwright/Vitest |
| `scripts/evaluate_v12_retrieval.py`, `run_v12_live_matrix.py`, fixture | Reproducible isolated replay and bounded append-only live evidence | generated JSON artifacts |
| `README.md`, `docs/api.md`, `CHANGELOG.md` | v1.2 behavior/API/operator documentation | documentation review |
| `package.json`, `package-lock.json`, `pyproject.toml`, API/web version files | Consistent `1.2.0` version | doctor, system API, build |
| `reports/mixed-source-cap-audit.*`, `source-verification.json`, all `reports/v1.2-*` files | Reproduced verification and release evidence | corresponding commands/tests |

No unrelated dependency was added. Generated Playwright HTML output is not part of the product evidence.

## Frozen component verification

Before and after SHA-256 values are identical:

- `ranking.py`: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py`: `751cb5ce34952c7907b45a94e5dd8419df8050929181093f0fa77a76b2136a90`
- `clustering.py`: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`

The 25% lexical / 75% semantic formula, semantic top-20 opportunity, <=1% combined secondary-quality budget, deterministic Phase 2 planner, and clustering semantics are unchanged. Phase 3 remains shadow-only.

## Required questions

**A. Did adaptive routing outperform production routing?** In deterministic replay it retained all labeled evidence while modeling 17 fewer requests (17.35%) and 4,400 ms aggregate expected latency reduction. This is promising, not sufficient production proof.

**B. Was it promoted?** No. **ADAPTIVE ROUTER REMAINS SHADOW** because multiple query classes lack sufficient independent cases.

**C. Did any query class lose meaningful evidence?** No fixture class lost labeled evidence; every per-class minimum recall was 1.0. Sample-size insufficiency remains explicit.

**D. How many useless requests were avoided?** Seventeen of 98 modeled production requests.

**E. Did time-to-useful-evidence improve?** Local evidence is now available internally after a mean 4.27 ms lane. Shadow routing estimates latency savings, but no production-routing or external-network speedup is claimed.

**F. Is local historical evidence first-class?** Yes. It is a typed, bounded LOCAL_MEMORY/HISTORICAL lane with exact/FTS narrowing and persisted coverage.

**G. Is local distinguishable from live?** Yes. Platform and acquisition path remain independent; local requests are always zero.

**H. Are publication and first observation distinct?** Yes; `published_at`, `first_seen_at`, `last_seen_at`, and `retrieved_at` have separate semantics and no publication date is fabricated.

**I. Are Arabic/English aliases evidence-bound?** Yes; support requires two independent sources, confidence >=0.8, explicit provenance, and bounded drift.

**J. Are ambiguous persons protected?** Yes; common single names are rejected and `علي فراس` receives no unsupported identity merge.

**K. Can MIRSAD say what it did not search?** Yes; persisted source rows and typed gaps show planner skips, bounded-round nonexecution, unavailable/restricted/unconfigured paths, and disabled web discovery.

**L. Can it distinguish all required gap categories?** Yes; current availability, restriction, configuration, disabled acquisition, execution failure, timeout/rate/circuit state, and no-match are distinct.

**M. Is ranking still the production architecture?** Yes. Frozen hashes and mixed-source invariance prove the unchanged 25/75 + <=1% architecture.

**N. Did operator data remain intact?** Yes. Integrity/FK/FTS pass; initial sessions/content remain; bookmarks=2 and saved searches=1 are preserved; only legitimate live validation growth occurred.

## Known limitations

- The adaptive replay is too small for production promotion, particularly outside Arabic topic/entity classes.
- Current public Bluesky access returned HTTP 403; configured does not mean currently healthy.
- SearXNG remains disabled, so X/Threads/Reddit web discovery remains disabled by operator choice.
- `@openai` and the future CVE query returned no live/local matches in the bounded matrix. Coverage explains this; no result is fabricated.
- Historical evidence is limited to content MIRSAD already observed and supported bounded index metadata. MIRSAD is not a generic crawler.
- No operator alias edge currently has enough live evidence to be supported; the mechanism is verified deterministically rather than populated speculatively.

## Verdict

MIRSAD v1.2 RETRIEVAL INTELLIGENCE VERIFIED
