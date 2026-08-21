# MIRSAD v1.1.1 Precision Hardening

Status: verified on 2026-08-21. The pre-change sections below were recorded before mutation and remain the baseline evidence.

## Verified baseline

- Branch: `v1.1.1-precision-hardening`
- HEAD: `f08627efeba1924d1a8eb00442880dfd89edad7b`
- Worktree before change: clean
- `ranking.py`: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py`: `e9b3485af310e6ed87f5e10e609e35496ff48c711a0299032b3f2fd40cdd0701`
- `clustering.py`: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`
- Operator database: `data/mirsad.db`, 9,232,384 bytes, SHA-256 `304e0caddf295bff76948a1a1c6ab287d26fd8461f7a8c348d634dbb5660f324`
- Operator backup: `/tmp/mirsad-v111-operator-20260821T035257Z.db`, SHA-256 `e2680bbc29e14cc6d6890cd529e534e957057711fb9850ff18dd81e76dbc7d49`
- Integrity: `ok`; foreign-key violations: 0; content/FTS: 785/785; sessions: 36; bookmarks: 2; saved searches: 1; clusters: 709

## Pre-change provenance reproduction

For the persisted v1.1 `بغداد` session, Bluesky was absent from planned and searched sources and emitted `source.skipped` with `not_selected`. The same event stream later emitted `source.progress` for Bluesky with 13 matched/admitted records, and two final results were Bluesky records. `mafer.rounds[0]` proves the execution began with 100 FTS local-memory candidates; 13 were from Bluesky. No memory-specific SSE event existed.

Root cause before change: `SearchService` placed `planning.local_memory.items` and connector items into one `items_by_source` map keyed only by platform. Candidate admission, `source.progress`, and connector final-count diagnostics then grouped the merged pool by platform. Persisted `ContentItem.acquisition_mode` described the record's original ingestion, not how the current search obtained it. Platform and per-execution acquisition path were therefore conflated.

## Pre-change intent reproduction

`الذكاء الاصطناعي` and `وزارة التخطيط` both emitted `PERSON_LIKE` at confidence 0.72. `Linux kernel security` emitted `PERSON_LIKE` at 0.64. The Arabic heuristic treated every unmarked 2–5-token Arabic phrase as name-like; organization detection missed normalized `وزاره`; the Latin title heuristic required only one capitalized token. Legitimate `علي فراس` and `علي فراس محمد رضا` also emitted `PERSON_LIKE`, so the fix must narrow evidence rather than remove Arabic name support.

## Pre-change visual audit

The audit used the actual v1.1 screenshots and running application, not a redesign mock.

- Completed desktop retained a roughly 230 px filter rail and 300 px trace rail, leaving the evidence column unnecessarily narrow after those rails stopped being operationally primary.
- Page, command bar, filter rail, trace, session summary, and every result were each boxed with similar borders and radii. Repeated card chrome flattened hierarchy and made evidence records resemble generic dashboard widgets.
- The command field was clear but visually competed with several same-weight bordered containers; active search state depended mostly on text and spinners rather than a coherent retrieval representation.
- Source state was truthful at the connector row level but had no distinct local-memory path, which contributed directly to the provenance contradiction.
- Results used numerous small badges and metadata tokens. Relevant snippets were useful, but titles, provenance, score, and actions had insufficient typographic separation at desktop density.
- Explain Score exposed real backend fields but visually treated secondary factors too much like peers of the 25/75 lexical-semantic core.
- The completed state showed substantial unused horizontal opportunity while the long result column increased page height and reading effort.
- Motion was largely absent except generic loading indicators. Search phases did not have a shared semantic transition system; there was no state-driven topology.
- Light mode was restrained and institutional, but surface levels were too similar. Dark mode required explicit validation rather than inversion assumptions.
- Arabic root direction worked, but the narrow center column amplified wrapping; technical identifiers, URLs, score values and source names required continued bidi isolation.
- Mobile/Sheet behavior was functional. Any visual engine must preserve DOM order, focus management, reflow and the existing zero-horizontal-overflow behavior.

The precision-instrument redesign will use line, rhythm, typography and real state before containers. It will not add generated visual assets, gradients, glass, particles, decorative networks, marketing copy, or continuous idle GPU work.

## Executive assessment

MIRSAD 1.1.1 resolves the v1.1 provenance contradiction, removes the demonstrated topic-as-person false positives, and ships bounded semantic preparation only after exact output-equivalence and measured critical-path improvement. The final ranker remains 25% lexical / 75% multilingual MiniLM over at most 20 semantic opportunities with at most 1% secondary quality influence. Phase 3 remains shadow-only.

The search UI is now state-adaptive: active work retains Filters / Results / Live Search, while completed and partial searches with results collapse both secondary rails and expand the evidence workspace. The user can reopen either rail without an immediate auto-collapse. Explain Score reflects the real mathematics and does not present relevance as probability or factual correctness.

No internal production blocker remains. Current Bluesky AppView access is externally forbidden from this environment; configuration and current health remain distinct, and local-memory Bluesky records remain independently usable without implying a live connector execution.

## Provenance correction

### Confirmed defect and root cause

The contradictory v1.1 Bluesky records came from SQLite FTS local memory, not the Bluesky connector. Session `f46c84b5-5cdc-4ba0-9da1-9b9448af5c62` began with 100 local-memory candidates, including 13 Bluesky records. `SearchService` merged those records with live items in a platform-keyed map and later emitted connector-oriented `source.progress` from that merged platform group. The persisted `ContentItem.acquisition_mode` described original ingestion, so it could not answer how this execution obtained the record.

### Implemented model

- `platform` remains the content platform (`bluesky`, `youtube`, and so on).
- `acquisition_mode` remains original ingestion provenance.
- `acquisition_path` and `acquisition_paths` describe this search execution.
- `LOCAL_MEMORY` is the single added acquisition value; it does not overlap with network acquisition modes.
- Typed `acquisition.local_memory.started/completed` events report local lookup latency, candidate/platform counts, and exactly zero network requests.
- Connector events remain limited to connector execution. A planned connector stopped before execution now receives `source.skipped/stopped_before_execution`, never a false completion.
- Diagnostics retain the legacy per-source funnel and add a platform-plus-acquisition funnel with separate local/network latency and request semantics.

### Deterministic and live proof

The regression constructs an unselected Bluesky connector plus admitted Bluesky local-memory results and proves zero Bluesky requests, no Bluesky start/completion event, `LOCAL_MEMORY` result provenance, and a separate funnel row. Live session `7859a8c3-4c20-41ba-8cbe-92d7db6dcfef` reproduced the same boundary: Bluesky was `not_selected`, emitted zero start/completion events and zero network requests, while 11 local Bluesky candidates were matched/admitted and 9 appeared in the final set. See `reports/precision-hardening-provenance.json`.

## Intent precision

The false positive arose from two broad rules: every otherwise-unmarked 2-5 token Arabic phrase was person-like, and a Latin phrase needed only one capitalized token. Normalization also converted `وزارة` to `وزاره`, which was missing from organization markers.

The narrow deterministic fix:

- recognizes both `وزارة` and normalized `وزاره` as organization evidence;
- rejects Arabic name inference when a small explicit topic-marker set is present;
- retains existing recent/historical/event exclusions;
- requires every literal Latin token to be title-cased before the existing title-like evidence applies.

No labels were made globally mutually exclusive. The regression matrix now produces:

| Query | Required outcome | Result |
| --- | --- | --- |
| `الذكاء الاصطناعي` | TOPIC, not PERSON_LIKE | pass |
| `وزارة التخطيط` | ENTITY/organization, not PERSON_LIKE | pass |
| `علي فراس محمد رضا` | PERSON_LIKE | pass |
| `علي فراس` | PERSON_LIKE | pass |
| `Microsoft العراق` | conservative entity/topic | pass |
| `Linux kernel security` | TOPIC, not PERSON_LIKE | pass |
| `@openai` | HANDLE literal preserved | pass |
| `#بغداد` | HASHTAG literal preserved | pass |
| `CVE-2026-61371` | IDENTIFIER punctuation preserved | pass |

Both required Arabic name cases remain person-like, so the demonstrated person-name cases did not regress. No broader name-recall claim is made from two fixtures.

## Semantic preparation

### Architecture and safety

`SemanticPreparationCoordinator` is per search, accepts at most 20 deduplicated cache identities, uses a bounded queue, and owns at most one asyncio producer task. All model work is serialized through the existing process-wide `ThreadPoolExecutor(max_workers=1)`, so FastEmbed/ONNX is never called concurrently. Preparation populates the existing model/version/content-hash cache only; query embeddings, candidate admission, final candidate selection, similarity, and scoring remain authoritative in the ranking stage.

Preparation candidates use the same cheap eligibility filters and fair per-source opportunity ordering as final semantic selection. A failure, cancellation, unsupported ranker, or model error is recorded and the normal ranking path continues. Search A/B metrics and task ownership are isolated; only content vectors valid under the existing global cache identity are reusable.

### Deterministic performance gate

`reports/precision-hardening-performance.json` uses the installed multilingual MiniLM, identical 20-candidate inputs, and 1,400 ms simulated network wait.

| Measurement | v1.1 sequential | v1.1.1 overlap |
| --- | ---: | ---: |
| Total wall time | 2,074.59 ms | 1,432.38 ms |
| Semantic critical path | 673.11 ms | 30.78 ms |
| Ranking cache hits/misses | 0 / 20 | 20 / 0 |
| Hidden semantic work | 0 ms | 620.34 ms |

Critical-path reduction was 642.22 ms (30.96%). Scores, similarities, and final order were exactly equal. RSS was 632.06 MB before inference, 669.73 MB after sequential inference, and 690.36 MB after the second overlap pass; allocator/model growth was 20.63 MB on that second pass, then 0.00 MB across three repeat jobs. The cache remained 20 entries under its existing 5,000-entry bound. This passes the ship gate.

### Real integrated observations

The five-query live matrix averaged 1,868.50 ms collection, 1,501.18 ms preparation, 1,264.91 ms hidden work, 698.97 ms remaining semantic critical path, and 3,301.80 ms total. External network variance dominates and these values are observations, not before/after causal claims. The final fair-selection `بغداد` run achieved 13 cache hits / 7 misses, hid 1,676.05 ms of preparation behind collection, and left 447.06 ms on the semantic critical path.

## Results-first workspace

- Idle is search-centric; active planning/collection/normalization/ranking/clustering uses the three-panel workspace.
- Terminal completed/partial searches with results hide desktop rails and widen results only after final ranked results stabilize.
- Filters and Trace remain available as accessible shadcn Sheets. Manual reopen survives normal terminal re-renders; a new search resets active layout.
- Medium/mobile remains single-column with Sheets and no horizontal overflow.
- Result records use separators and typography instead of nested marketing cards, expose platform and acquisition path separately, retain canonical URL and bidi isolation, and preserve safe React-node highlighting.
- Final results receive only a short bounded reveal for the first visible items; ranking order is never animated or recomputed.

## Explain Score

The Sheet reads authoritative backend explanation fields. It renders Final Relevance, then the 25% lexical and 75% semantic core, then one visually subordinate secondary-adjustment section labeled with the maximum 1% total budget, followed by penalty. Secondary signal values are not shown as peers of the core. A lexical-only result displays `Semantic reranking was not applied` and no fabricated semantic percentage. The explanation explicitly says relevance is not probability or factual correctness.

## Visual Engineering

### Design audit and hierarchy

The pre-change audit identified narrow completed results, nested/repetitive cards, same-weight surfaces, badge overuse, a weak search-stage visual model, and secondary score factors with excess visual weight. The new hierarchy is Navigation -> Search Instrument -> Session State -> Evidence Workspace -> Secondary Analysis. Evidence records use lines, baseline alignment, technical type treatment, controlled spacing, and semantic surface tokens rather than giant rounded containers.

No image-generation tool or generated visual asset was used. The final UI contains no gradient hero, glass, glow, particle field, floating blob, magic iconography, marketing copy, or random topology.

### GSAP architecture

`lib/motion.ts` lazy-loads GSAP and centralizes duration/ease tokens. Scoped `gsap.context()` plus `matchMedia()` owns SVG flow, result reveal, and workspace transitions; effects revert on unmount. Motion represents state changes only. Empty target sets are checked before animation, removing GSAP console warnings. `prefers-reduced-motion` replaces movement with static state.

### SVG architecture

`RetrievalFlowSvg` displays only actual connector and local-memory states moving through MAFER, normalization, ranking, and evidence. Active/completed/failed paths use text/icon/state plus color. The inline SVG has `<title>`, `<desc>`, `aria-labelledby`, and no retrieved HTML.

### Three.js / WebGL lifecycle

One dynamically imported Three.js renderer is mounted only inside the visible live trace. It uses shallow source/core/evidence primitives derived from typed state, capped DPR 1.5, no textures, no postprocessing, no imported assets, and no pointer interception. A local-memory node is independent of platform connector nodes. ResizeObserver owns sizing; Page Visibility pauses rendering; terminal and reduced-motion states render on demand. Context loss switches to the structured SVG/static fallback and triggers renderer cleanup. Geometry, materials, listeners, animation loop, canvas, and renderer are disposed on unmount.

The final real-browser sample recorded 15 draw calls, 1,076 triangles, 15 geometries, and zero textures. Thirty frames averaged 22.53 ms with a 66.80 ms maximum and six frames over 25 ms; no 60 FPS claim is made. Three repeated trace mounts ended with canvas counts `[0,0,0]`; observed heap stayed 76,600,000 bytes before/after. Forced fallback rendered zero canvases. See `reports/precision-hardening-visual.json`.

### Bundle impact

| Asset | v1.1 raw / gzip | v1.1.1 raw / gzip |
| --- | ---: | ---: |
| Main | 267.57 / 85.68 kB | 266.53 / 85.27 kB |
| Search route | 49.12 / 12.64 kB | 61.77 / 16.44 kB |
| CSS | 127.15 / 26.74 kB | 132.69 / 27.71 kB |
| GSAP lazy chunk | absent | 69.96 / 27.42 kB |
| Three.js lazy chunk | absent | 724.23 / 184.67 kB |
| Topology component | absent | 5.63 / 2.38 kB |

The search input and base route do not await Three.js. The Three chunk is large but isolated, optional, and loaded only when the live topology mounts. Current result limits do not justify virtualization.

### Screenshots and accessibility

Fourteen required state screenshots plus one lexical-only explanation are in `reports/precision-hardening-screenshots/`: light/dark idle, active topology/SVG/ranking, results-first completion, Trace open, semantic-ready/lexical-only score, local-memory provenance, Arabic active/completed, mobile, reduced motion, and WebGL fallback. Guarded live Playwright passed with zero captured console errors, page errors, WebGL errors, React warnings, or GSAP warnings. The isolated E2E accessibility/keyboard/RTL suite also passed.

Primary implementation research and applied decisions are recorded in `reports/design-research-sources.md` using official GSAP, Three.js, MDN, WCAG 2.2, and shadcn sources.

## Live matrix

`reports/precision-hardening-live-matrix.json` contains five bounded public-data executions. Four completed and `وزارة التخطيط` was partial while retaining 30 results. The matrix plus visual validation produced 10 legitimate persisted live sessions in total; no database reset occurred. Repeated visual runs were bounded to resolving incorrect pre-existing evidence-session IDs, not repeated source-health probing.

| Query | Intent (abbreviated) | Status | Results | Collection | Hidden semantic | Semantic critical | Total |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `الذكاء الاصطناعي` | ARABIC, TOPIC | completed | 30 | 996.19 ms | 981.89 ms | 1,339.10 ms | 3,007 ms |
| `وزارة التخطيط` | ARABIC, ENTITY, TOPIC | partial | 30 | 4,012.83 ms | 1,092.55 ms | 513.94 ms | 4,964 ms |
| `Linux kernel security` | ENGLISH, TOPIC | completed | 30 | 1,425.04 ms | 1,370.61 ms | 620.90 ms | 2,897 ms |
| `OpenAI` | ENGLISH, AMBIGUOUS, TOPIC | completed | 30 | 1,210.75 ms | 1,203.43 ms | 573.87 ms | 2,381 ms |
| `بغداد` | ARABIC, AMBIGUOUS, TOPIC | completed | 30 | 1,697.68 ms | 1,676.05 ms | 447.06 ms | 3,260 ms |

The live JSON includes selected/searched/skipped sources, event sequence, connector and acquisition funnels, request variants, result counts, stops, warnings, cache metrics, and top records. No P@K claim is made.

## Source and failure isolation

One bounded source verification at `2026-08-21T06:50:28Z` produced:

- PASS: Hacker News public endpoint, GitHub anonymous API, YouTube credentials, Mastodon public timeline; RSS and GDELT local configuration.
- External failure: Bluesky is configured but both public probe attempts returned HTTP 403. It is not relabeled unconfigured or internally failed.
- Disabled/unconfigured: SearXNG remains disabled, so X/Threads/Reddit web discovery remains disabled rather than connector-failed.
- Restricted sources remain restricted. No CAPTCHA bypass, login automation, proxy rotation, or arbitrary URL fetch was introduced.

Healthy-source records survived the live partial query. Planned sources stopped after the evidence/limit gate now show `stopped_before_execution`, which prevents a selected count from implying that a network request occurred.

## Security

A focused working-tree review covered the new SSE payloads, job ownership boundaries, SQLite migration, provenance fields, semantic worker/queue, React rendering, GSAP selectors, SVG, Three.js lifecycle, Playwright guard, and fixed report paths. Events contain enum/source/count/timing metadata only; no exception dump, key, token, target URL, filesystem path, or retrieved HTML was added. Job IDs remain opaque UUIDs and no endpoint accepts a fetch target.

Security/export/manual-import/source-verification/job tests passed. `dangerouslySetInnerHTML` remains absent from retrieved-content paths (the existing shadcn chart component uses it only for locally constructed theme CSS). Source scanning found no embedded credential assignment, `npm audit` found 0 vulnerabilities, CSV escaping and URL/manual-import boundaries pass, and `git diff --check` is clean. No reportable security regression was found. TAC status could not be checked because the hosted advisory connector was unavailable in this terminal; this did not change the local source/test result.

## Tests and operational validation

| Gate | Result |
| --- | --- |
| Backend Pytest | 223 passed |
| Frontend Vitest | 34 passed across 10 files |
| Isolated Playwright | 11 passed, 6 explicit opt-in live tests skipped |
| Guarded live Playwright | workspace/search test passed; context-loss cleanup test passed; no reset |
| Ruff | pass |
| Oxlint | pass |
| TypeScript | pass |
| Vite production build | pass |
| Deterministic overlap benchmark | ship; exact scores/similarities/order |
| Mixed-source completion-order invariance | pass |
| SQLite integrity / FK / FTS parity | `ok` / 0 / 842=842 |
| Doctor | pass; optional SearXNG warning only |
| Source verification | exit 0; Bluesky external 403 recorded |
| Startup/readiness/shutdown | pass through bounded same-process smoke |
| Restart persistence | content/sessions/bookmarks/saved counts unchanged across smoke |
| npm audit / secret pattern scan | 0 vulnerabilities / no credential candidates |

The initial full E2E run found one ambiguous `mock` table locator after the acquisition table was added. The table received a localized accessible name and the assertion was scoped to the source funnel. A separate console review found GSAP empty-target warnings; the SVG motion primitive now checks target counts. Targeted reruns passed, followed by the final full isolated suite.

## Frozen verification

| Component | Before | After | Result |
| --- | --- | --- | --- |
| `ranking.py` | `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4` | same | byte-identical |
| `semantic.py` | `e9b3485af310e6ed87f5e10e609e35496ff48c711a0299032b3f2fd40cdd0701` | `751cb5ce34952c7907b45a94e5dd8419df8050929181093f0fa77a76b2136a90` | preparation/instrumentation only; exact scoring equivalence |
| `clustering.py` | `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63` | same | byte-identical |

The historical `reports/mafer-phase2-benchmark.json` was regenerated by a test during validation and then restored to HEAD exactly; it has no final diff. No 25/75, top-20, <=1%, clustering, routing production strategy, or Phase-3 promotion change occurred.

## Operator database integrity

| Measure | Before | After |
| --- | ---: | ---: |
| Size | 9,232,384 bytes | 11,714,560 bytes |
| SHA-256 | `304e0caddf295bff76948a1a1c6ab287d26fd8461f7a8c348d634dbb5660f324` | `f1607dde4bd0d4be660e5c7b9dad42203c15c1d682da2c1d41a8454e3c34f2d0` |
| Content / FTS | 785 / 785 | 842 / 842 |
| Sessions | 36 | 46 |
| Bookmarks | 2 | 2 |
| Saved searches | 1 | 1 |
| Clusters | 709 | 1,011 |

Final `integrity_check=ok`, foreign-key violations are 0, and FTS parity is exact. Growth is attributable to the bounded live campaign; no prior row category decreased. The immutable backup remains readable at `/tmp/mirsad-v111-operator-20260821T035257Z.db`, SHA-256 `e2680bbc29e14cc6d6890cd529e534e957057711fb9850ff18dd81e76dbc7d49`, with the original logical counts. No reset or delete was run against operator state.

## Files changed

| File | Reason and behavior | Coverage |
| --- | --- | --- |
| `apps/api/mirsad_api/provenance.py` | adds the single `LOCAL_MEMORY` path | provenance regression |
| `connectors/base.py` | carries current-search acquisition path independently | provenance regression |
| `mafer/memory.py` | labels FTS/discovery-memory candidates local | provenance regression |
| `models.py`, `database.py` | additive nullable per-result path/path-set persistence | DB/full API tests |
| `schemas.py`, `services/read_models.py` | typed event/result/semantic-state contract | job/read-model/frontend tests |
| `services/search.py` | truthful memory/live funnels and events; bounded preparation integration | provenance, jobs, invariance, full suite |
| `domains/semantic.py` | same-cache preparation entry point and stats | cache/equivalence/fallback tests |
| `services/semantic_preparation.py` | bounded one-worker per-search coordinator | bound/dedup/isolation/cleanup tests |
| `mafer/intent.py` | conservative topic/org/person gating | intent matrix |
| API tests (`test_mafer_intelligence.py`, `test_search_jobs.py`, `test_semantic.py`) | deterministic regressions for all backend changes | 223-test suite |
| `apps/web/src/types/api.ts` | mirrors typed path and event fields | TypeScript/Vitest |
| `lib/search-job-state.ts` and test | memory/preparation/stopped-source state without stale terminal mutation | reducer tests |
| `lib/motion.ts` | lazy centralized GSAP tokens | build/browser cleanup |
| `retrieval-flow-svg.tsx` | accessible real-state SVG topology | live/reduced-motion E2E |
| `retrieval-topology-3d.tsx` | bounded lazy WebGL topology and lifecycle | live/fallback/lifecycle E2E |
| `live-search-trace.tsx` and test | separate local-memory lane and real source states | component/E2E |
| `search-page.tsx`, `workflows.test.tsx` | state-adaptive results-first workspace | workflow/live E2E |
| `search-form.tsx` | precision-instrument command hierarchy | responsive E2E |
| `result-card.tsx` and test | evidence layout, explicit provenance, truthful score sheet | result tests/live E2E |
| `search-diagnostics.tsx`, `mirsad.spec.ts` | acquisition funnel and accessible source-funnel scope | isolated E2E |
| `index.css`, `i18n.tsx` | semantic tokens, bidi/reduced motion, all localized strings | RTL/unit/E2E |
| `package.json`, lockfiles, version/config/layout files | GSAP/Three dependencies and version 1.1.1 | audit/build/system tests |
| `README.md`, `docs/api.md`, `CHANGELOG.md` | documents runtime contract and limitations | documentation review |
| `scripts/benchmark_precision_hardening.py` | deterministic overlap gate | performance JSON |
| `scripts/search_evolution_live_matrix.py` | exports new path/preparation telemetry | live matrix |
| `scripts/evaluate_mafer_planning.py`, `test_mafer_planning_benchmark.py` | prevents tests from rewriting immutable Phase-2 evidence | benchmark regression and clean Git diff |
| `reports/source-verification.json` | bounded current source states | verify-sources |
| precision reports, design research, screenshots | reproducible evidence | machine-readable/manual review |

## Required answers

- **A:** The Bluesky records came from SQLite FTS local memory.
- **B:** Yes. Platform, original ingestion mode, and per-execution acquisition path are distinct.
- **C:** No. Local-memory content cannot turn an unselected connector into completed.
- **D:** The Arabic heuristic treated every unmarked 2-5 token phrase as person-like.
- **E:** Normalized organization evidence plus a narrow topic-marker exclusion and all-token Latin title casing.
- **F:** No regression in the required legitimate Arabic person fixtures; both pass.
- **G:** Yes, one bounded preparation worker overlaps the existing connector I/O.
- **H:** 620.34 ms moved off the controlled critical path; live observations hid 981.89-1,676.05 ms depending on query.
- **I:** No. Controlled scores, similarities, and ordering are exactly equal.
- **J:** No steady-state material regression was observed: second-pass RSS added 20.63 MB, then repeat-job growth was 0.00 MB.
- **K:** Yes. Terminal desktop state collapses rails and prioritizes wide results.
- **L:** Yes. Explain Score renders the 25/75 core, a subordinate <=1% adjustment, and penalty from backend data.
- **M:** Yes. Integrity/FK/FTS pass; bookmarks and saved searches remain intact; the backup remains readable.

## Known limitations

- Bluesky is configured but currently externally HTTP-403-limited from this environment; local memory remains available and is labeled as such.
- Semantic overlap effectiveness depends on candidate-set agreement and available connector wait. It is non-fatal and cannot eliminate all cold inference.
- The lazy Three.js chunk is 184.67 kB gzip. It is isolated from the initial interactive path and has SVG/static fallback.
- The measured visual frame sample included six intervals above 25 ms; the topology stays deliberately small, terminal rendering stops, and no 60 FPS claim is made.
- The topic marker set is deliberately small to avoid overfitting; broader person/entity recall requires separately judged data.

## Verdict

MIRSAD v1.1.1 PRECISION HARDENING VERIFIED
