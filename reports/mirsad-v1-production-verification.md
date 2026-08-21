# MIRSAD v1.0 Production Verification

Generated: 2026-08-10 (Asia/Baghdad)  
Release: `1.0.0`

## Production Configuration

MIRSAD ships the verified deterministic MAFER Phase 2 planner. The authoritative final ranker remains
25% lexical / 75% local multilingual MiniLM, with at most 20 semantic candidates and a 1% bounded
secondary-quality budget. Phase 3 routing, stopping, query-aware fusion, MPNet, and near-tie diversity
remain shadow-only. No shadow output can change connector selection, candidate admission, or visible
ordering.

The frozen production files were hash-verified after all release work:

| File | SHA-256 |
| --- | --- |
| `ranking.py` | `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4` |
| `semantic.py` | `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24` |
| `clustering.py` | `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63` |

## Production Repairs

- `start.sh` now starts the bundled localhost SearXNG container when `SEARXNG_ENABLED=true`, performs a
  bounded JSON-search readiness check, and leaves direct/public collection available when upstream
  engines are blocked. `stop.sh` stops only a SearXNG instance managed by that startup invocation.
- A minimal localhost browser-capture companion imports an operator-selected public X/Threads/Reddit
  post URL and visible text. The backend uses the existing strict classifiers, performs no page fetch,
  stores null engagement metrics, canonicalizes/deduplicates, and records `MANUAL_IMPORT` provenance.
- A bounded real-record evaluator and automatic-routing live smoke now produce reproducible,
  machine-readable production evidence. Seed targets are rejected from evaluation memory before each
  known-item case.

No ranking, semantic, clustering, relevance threshold, or candidate-strategy change was made.

## Real Public-Data Evidence

The bounded campaign made at most 90 capture requests and 100 known-item requests; it did not retry
blocked providers indefinitely. It collected 480 real public records with canonical URLs:

| Segment | Count |
| --- | ---: |
| Arabic | 102 |
| English | 248 |
| Mixed Arabic/English | 130 |
| YouTube | 215 |
| Bluesky | 157 |
| Hacker News | 78 |
| Mastodon | 30 |

Corpus SHA-256: `aa2c627f0aab822c53f76b9599d400b9d25bb0167e944753dd7c2b5058bb3dd0`.
The frozen 100-case positive-only known-item set contains 40 Arabic, 45 English, and 15 mixed cases.
It contains 56 distinctive exact phrases, 36 handles, and 8 hashtags. These labels establish only a
known positive target; they are not complete relevance judgments and therefore are not reported as
Precision@K.

| Metric | Result |
| --- | ---: |
| Completed cases | 99 / 100 (one external Bluesky 403) |
| KnownItemRecall@1 | 0.4141 |
| KnownItemRecall@5 | 0.4949 |
| KnownItemRecall@10 | 0.5051 |
| KnownItemMRR | 0.4496 |
| Exact-phrase KnownItemRecall@5 | 0.8393 |
| Exact-phrase KnownItemRecall@10 | 0.8571 |

Handle known-item recovery was 0/35: current public search endpoints generally do not rediscover a
specific post from an author handle alone. This is a measured discovery limitation, not evidence that
an admitted item ranked poorly. The 118-item local judgment queue prioritizes production/shadow
disagreements and Arabic uncertainty, permits `Skip / Unsure`, and does not reveal strategy identity
before judgment.

## Arabic Loss Funnel

The Arabic-inclusive funnel contained 55 known targets: 54 live requests completed, 32 targets were
rediscovered, and all 32 were canonicalized, locally matched, admitted, and given semantic opportunity
(or the intentional literal-query lexical path). Thirty-one ranked in top 5 and top 10.

The observed loss is therefore 22 external rediscovery misses plus one external request failure; there
is no systematic internal candidate-admission loss in this sample. Among completed Arabic cases,
KnownItemRecall@5/10 was `0.6410` and KnownItemMRR was `0.5992`. A ranking or Arabic-normalization
change was not justified by these results.

## Live Searches And Sources

Eight no-mock automatic-routing searches covered Arabic entity/topic/exact phrase, English
entity/topic, mixed language, hashtag, and identifier intents. They persisted 391 unique content items
to an isolated 3.5 MiB database. Result latencies ranged from 272 ms (warm local-memory reuse) to
6,547 ms (mixed healthy and degraded network sources); local semantic reranking remained bounded and
ready. The hashtag literal path correctly reported `lexical_only` rather than a failed semantic model.

Live readiness at release time:

- `LIVE`: YouTube (configured API key), Bluesky public AppView, Mastodon configured-instance public
  timeline, GitHub anonymous API, Hacker News public API, RSS configuration, GDELT configuration.
- `OPTIONAL_CREDENTIAL`: X, Threads, Telegram, Reddit, Instagram.
- `RESTRICTED`: TikTok Research, Facebook, LinkedIn.
- `DEGRADED_EXTERNAL`: GDELT timed out/circuit-broke in some live searches; later-page Bluesky 403s
  occurred; failures remained isolated and healthy-source results were retained.

## SearXNG

One low-volume campaign successfully reached the localhost JSON API in 901 ms. Brave was rate-limited;
DuckDuckGo, Qwant, and Startpage reported CAPTCHA. Application state was correctly
`DEGRADED_EXTERNAL`, not an application failure. No blocked engine was retried, no CAPTCHA bypass or
proxy rotation was attempted, and SearXNG remains optional. The explicit browser capture is the
non-automated fallback.

## Shadow Promotion Decisions

| Component | Decision | Reason |
| --- | --- | --- |
| Calibrated stop/uncertainty | `KEEP_SHADOW` | Live positive-target and unjudged pool evidence is insufficient to prove request/quality trade-offs. |
| Query-aware fusion | `KEEP_SHADOW` | Controlled evidence remains promising, but the live pool lacks complete independent judgments. |
| Adaptive router | `KEEP_SHADOW` | No production-quality local feedback volume yet. |
| MPNet Arabic expert | `KEEP_SHADOW` | Real loss is primarily discovery; its approximately 1.1 GiB footprint is not justified. |
| Near-tie diversity | `KEEP_SHADOW` | No independently judged live benefit. |

No Phase 3 component was promoted. The verified configuration snapshot remains authoritative and the
tested one-step rollback remains available without altering stored content.

## Source Fairness

The 11-query mixed-source audit covered Arabic, English, hashtags, and mixed language. Each source
received its bounded pre-candidate and semantic opportunity before the final cap. Reversing source
request and connector completion order produced identical final identities and ordering for every
query. No source quota or forced diversity was introduced.

## Security

The deterministic security suite covers strict platform URL classification, schemes/credentials/IP
hosts, confusable domains, redirects, fixed SearXNG/Common Crawl/oEmbed boundaries, safe official
embed handling, SQL-bound feedback/import input, request limits, and secret-safe API projections.
Manual import rejects profile/non-content/private-host URLs and never fetches the submitted target.
The production bundle contains no connector secret variable names. Retrieved content is rendered as
text; the only `dangerouslySetInnerHTML` usage is shadcn Chart's application-owned static theme CSS.

## Clean Validation

| Gate | Result |
| --- | --- |
| Dependency sanity | npm trees valid; `pip check` reports no broken requirements |
| Compose | default and `mafer` profile configurations valid |
| Doctor | PASS; optional disabled SearXNG reported WARN |
| Source verification | PASS for all configured direct/public sources; optional/restricted sources WARN |
| Backend | 198 passed |
| Frontend | 21 passed in 6 files |
| Playwright | 11 passed, 2 opt-in live tests skipped |
| Browser/RTL/accessibility | route crawl, 20 locale switches, portals, stale requests, axe, and bounded memory observation passed |
| Lint / TypeScript / build | PASS / PASS / PASS |
| Mixed-source cap | 11/11 order-invariant queries; `MIXED-SOURCE CAP VERIFIED` |
| Database | `integrity_check=ok`, zero FK violations, FTS insert/update/delete/rebuild tests pass |
| Startup/shutdown | doctor + API + frontend ready; measured startup 1.65 s; clean PID shutdown |
| Bundle secret scan | clean |

The first standalone startup invocation was terminated when its approved execution shell ended; the
same-shell bounded smoke proved service readiness and shutdown, so this was execution-harness process
cleanup rather than an application detachment defect.

## Known Limitations

- Real known-item metrics measure rediscovery of one known positive, not comprehensive topical
  precision. Human judgments remain required before adaptive promotion.
- Web-index engines may rate-limit or present CAPTCHA; MIRSAD does not bypass them.
- X/Threads/Reddit direct APIs and other restricted platforms still require legitimate credentials or
  approval. Mastodon coverage remains instance-scoped and recent.
- GDELT and Bluesky can degrade transiently; bounded timeouts/circuit behavior isolate their failures.
- The existing shadow MPNet model occupies approximately 1.1 GiB locally but is not loaded or used by
  production. The production MiniLM model occupies approximately 241 MiB.

## Evidence

Machine-readable artifacts are in `reports/production-evidence/`, principally:

- `summary.json`
- `real-corpus.json`
- `known-item-cases.json`
- `known-item-evaluation.json`
- `known-item-analysis.json`
- `live-connector-telemetry.json`
- `live-search-smoke.json`
- `judgment-queue.json`
- `searxng-engine-health.json`

Historical architecture and calibration evidence remains in the existing Phase 1/2/3 reports and was
not rewritten for the `1.0.0` release.

## Release Decision

All internal production gates pass. External restrictions remain explicit and isolated. Release
metadata is consistently `1.0.0`; `CHANGELOG.md`, `.env.example`, runtime documentation, and API docs
describe the shipped behavior.

**MIRSAD v1.0 PRODUCTION READY**
