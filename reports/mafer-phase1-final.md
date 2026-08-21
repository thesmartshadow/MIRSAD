# MAFER Phase 1 Final Report

Date: 2026-08-10  
Application: MIRSAD `1.0.0-rc1`  
Phase: MIRSAD Adaptive Federated Evidence Retrieval, free federated discovery foundation

## Architecture Before / After

The pre-change pipeline and immutable baselines are recorded in
`reports/mafer-phase1-baseline.md`. Search still follows the existing connector-to-normalization,
SQLite/FTS5, local MiniLM, explainable score, deduplication, clustering, analytics, API, and
shadcn UI path.

Phase 1 adds `mirsad_api/discovery` as a bounded acquisition boundary used by the existing X,
Threads, and Reddit adapters when their direct credentials are absent. Platform-specific URL
rules remain in classifiers and do not leak into ranking. The connector contract and content
model now carry acquisition provenance independently from source:

- `DIRECT_API`
- `PUBLIC_API`
- `PUBLIC_TIMELINE`
- `WEB_INDEX`
- `HISTORICAL_INDEX`
- `OFFICIAL_EMBED`
- `MANUAL_IMPORT`

The authoritative ranking, semantic, and clustering files retain their baseline SHA-256 hashes.
The lexical admission, bounded top-20 local MiniLM rerank, 25/75 relevance blend, and 1% secondary
quality budget were not changed.

## SearXNG State

`infra/searxng` provides an optional official SearXNG container deployment. It binds only to
`127.0.0.1:8080`, enables the JSON API, mounts read-only settings, persists only the SearXNG cache,
uses no paid engine, proxy rotation, Tor, CAPTCHA solver, or login automation, and is contacted
only by FastAPI. Both the dedicated and root Compose configurations validate successfully.

Backend configuration is `SEARXNG_ENABLED` and `SEARXNG_URL`; timeouts, engine selection, cache
TTL, result limits, and query-variant limits are backend-only bounded settings. Doctor validates
the infrastructure and probes the actual JSON search endpoint when enabled.

## Enabled Upstream Engines

The local profile enables Brave, DuckDuckGo, Qwant, and Startpage from SearXNG's official engine
definitions. A first low-volume live probe returned indexed results through Brave and DuckDuckGo;
Startpage reported a CAPTCHA. Subsequent probes from the same environment observed:

| Engine | Final live state | MIRSAD behavior |
| --- | --- | --- |
| Brave | Rate limited / suspended | Per-engine `rate_limited`; no retry bypass |
| DuckDuckGo | CAPTCHA | Per-engine error; no solving or circumvention |
| Startpage | CAPTCHA / suspended | Per-engine error; no solving or circumvention |
| Qwant | No useful result in the final probe | Remained a configured bounded engine |

SearXNG itself remained reachable and returned valid JSON. Its health probe correctly reports
`upstream_engines_unavailable` when HTTP 200 contains zero results and only upstream failures.

## Engine Health And Telemetry

Every discovery run preserves engine, query variant, target platform, latency where provided,
returned count, target-domain count, accepted canonical count, duplicates, timeout, rate-limit,
and safe error text. HTTP 200 with upstream failures is exposed as degraded even when no canonical
records are accepted. This telemetry describes discovery usefulness, never truth or reliability.

The final live degraded search completed all three web connectors in 230.03 ms of connector wall
time and 239 ms total. Completion order was Reddit, X, Threads. Each source returned HTTP 200 from
local SearXNG, zero records, and a structured `partial_engine_failure`; the session returned no
fabricated data and its JSON export contained zero records.

## X Web Discovery

Without `X_BEARER_TOKEN`, the registered X connector uses the shared `WEB_INDEX` path only when
SearXNG is enabled. It generates a bounded domain-constrained query, then independently accepts
only canonical public post forms on `x.com` or `twitter.com`. Profile, navigation, wrong-domain,
credential-bearing, IP-host, confusable-domain, and unsafe-scheme URLs do not enter the post path.
Diagnostics and UI state explicitly say indexed public web coverage, not X API search.

The deterministic suite proves post/profile separation, alias canonicalization, multi-engine
support, Arabic content, malformed payload, 429, timeout, cache, and partial upstream failure. The
final live engine state yielded no accepted X record; this is an external discovery limitation,
not represented as API support or replaced with mock data.

## Threads Web Discovery

Without a Threads access token, the registered connector uses the same bounded discovery service.
The classifier supports current public `threads.com`/`threads.net` post forms and separates posts,
profiles, and other navigation. Diagnostics and UI explicitly distinguish web-index discovery
from Threads API search.

The deterministic shared-connector suite proves a real connector item with `WEB_INDEX`
provenance. The final live upstream state yielded no accepted Threads record and was reported as
degraded rather than silently successful.

## Reddit Web Discovery

Without approved OAuth credentials, Reddit uses the shared `WEB_INDEX` path when enabled. URL
classification separates public posts, comments, communities, profiles, and unrelated paths.
Only posts and comments enter normal content discovery; no Reddit Data API or hidden structured
endpoint is used.

During low-volume implementation validation, the `technology` query produced two real public
Reddit records through DuckDuckGo. Both records were canonicalized, normalized, persisted,
admitted to FTS5, ranked, clustered, exposed through the result API, and exported with
`WEB_INDEX` provenance and null unavailable metrics. That session completed in 1.742 seconds;
semantic reranking took 697.24 ms and database persistence took 12.63 ms. Later probes were
blocked by upstream rate-limit/CAPTCHA state and correctly returned zero.

## Canonicalization

The classifiers use parsed hostnames rather than trusting `site:`. They normalize known aliases,
strip tracking parameters/fragments, preserve stable public identifiers, force canonical HTTPS,
and reject unsupported schemes, credentials, IP/private hosts, confusable Unicode hostnames,
wrong domains, search/home pages, and profile/community pages where post content is required.
Multiple engines and variants that discover one canonical URL create one discovery record and
independent observations rather than duplicate content.

## Official Embed Enrichment

Optional enrichment is available only after platform URL validation and only through fixed
official X and Reddit oEmbed endpoints. Threads enrichment reports unavailable. Provider HTML is
discarded; the backend retains only safe attribution metadata and never executes embed HTML or
fabricates engagement, verification, or publication timestamps. Enrichment is not used as a
search mechanism and remains disabled by default.

## Local Discovery Memory

SQLite now stores canonical discovery records, independent engine/query observations, and bounded
cache entries. Memory retains platform, stable identifier, acquisition, indexed title/snippet,
first/last seen by MIRSAD, content fingerprint, completeness, and availability state. Discovery
Support is the count of independent engine/variant observations for one canonical URL; it is
exported and diagnosed but is not a truth/credibility score or an unbounded ranking input.

Discovery memory is deliberately separate from `content_fts`: only connector items admitted by
the normal content pipeline enter FTS5. Insert/reuse/cascade and cache behavior have deterministic
database coverage.

## Common Crawl Historical Mode

The optional adapter is disabled by default. It uses the current documented Common Crawl index,
accepts only an already validated exact public platform URL, and retrieves a bounded amount of
capture metadata. It does not download WARC data and is never invoked for ordinary keyword
searches. Results are labeled `HISTORICAL_INDEX`; this is historical capture evidence, not live
platform search or current availability proof.

## Cache Behavior

The cache key includes normalized query, variants, platform, language, time scope, selected
engines, limit, and historical mode. TTL and entry/result counts are bounded. Diagnostics expose
`fresh`, `cached`, `refreshed`, or `stale_fallback`; stale data is not hidden as fresh. A regression
test expires a real cache row, injects a provider timeout, and proves explicit stale fallback.

## Source-Cap Invariance

The previous global truncation before authoritative scoring was removed. Each selected source now
receives a bounded pre-candidate opportunity, the union is canonicalized and deduplicated, and the
global result cap is applied only after FTS/BM25, the unchanged bounded semantic stage, explainable
scoring, and duplicate-aware ordering.

`reports/mixed-source-cap-audit.md` contains an 11-query audit across English, Arabic, hashtags,
and mixed Arabic/English. Each query was executed twice with source request order and connector
completion order reversed. Results:

- All 11 completion-order shuffles produced identical final identities and order.
- Every matched source retained admitted candidates.
- The six source-shaped fixture pools remained visible where relevance justified them.
- Final source counts were not equalized or quota-forced.

The audit also found that title-bearing sources could consume all bounded semantic evaluation
slots while comparable titleless social items remained on a lexical-only score scale. The frozen
top-20 limit and 25/75 fusion remain unchanged; deterministic round-robin selection across each
source's lexical queue now allocates evaluation opportunity, not final positions. Global relevance
still determines the final cap.

## Security Review

- SearXNG and Common Crawl URLs are server configuration, never search-request parameters.
- Generic discovery never fetches a candidate platform page.
- oEmbed endpoints are fixed and receive only validated canonical URLs.
- HTTP redirects are disabled for SearXNG, Common Crawl, and embed requests.
- Classifiers reject unsafe schemes, credentials, IP/private hosts, IDN confusables, wrong hosts,
  and non-content URL forms.
- Indexed snippets are rendered as text; no discovery HTML is sent to the UI.
- External metrics remain null when the index does not provide them.
- Secrets are absent from API/read models, diagnostics, exports, frontend code, and logs.
- SearXNG is localhost-bound and the frontend has no SearXNG transport path.
- No prohibited frontend component framework was introduced; presentation remains shadcn/Tailwind.

## Performance

- Deterministic 11-query mixed-source audit: 48 matched fixture records per normal query, bounded
  50-per-source admission, 20 semantic candidates, and 30 final results.
- Final fully degraded live web search: 230.03 ms connector collection; 239 ms total; no retries or
  fabricated fallback.
- Earlier live Reddit-positive run: 1.742 s total, including 697.24 ms local semantic reranking and
  12.63 ms persistence.
- Discovery requests are bounded to at most three variants and 100 results; SearXNG has one
  bounded attempt, no redirects, and no unlimited retry path.
- URL validation/deduplication uses canonical hash/map lookup rather than unbounded pairwise fetch
  or comparison.

## Validation

Fresh final commands and observed results:

| Check | Result |
| --- | --- |
| `npm run test:api` | 158 passed |
| `npm run test:web` | 6 files, 17 tests passed |
| `npm run test:e2e` | 11 passed, 2 opt-in live tests skipped |
| `npm run lint` | Ruff and Oxlint passed |
| `npm run typecheck` | TypeScript passed |
| `npm run build` | Vite production build passed, 2,769 modules transformed |
| `npm run audit:mixed-source-cap` | 11/11 exact completion-order invariant |
| `npm run doctor` | No failures; SearXNG-disabled state reported as WARN |
| `npm run verify-sources` | Command passed; public/direct state matched configuration |
| `npm run reset-db` | Database recreated successfully |
| SQLite checks | `integrity_check=ok`, no FK violations, FTS/content counts synchronized |
| Compose validation | Root and `infra/searxng` configurations passed |
| Startup smoke | API health 200, frontend HTML loaded, clean logs, graceful stop |

Playwright covered search, score explanation, diagnostics, history, saved searches, bookmarks,
exports, all major routes, narrow viewport, accessibility, all production portal primitives,
EN/AR switching, stale-request isolation, and bounded resource stress. The test browser reported no
unexplained console errors.

The frozen hashes remained unchanged after all implementation and validation:

- `ranking.py`: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py`: `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24`
- `clustering.py`: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`

## Live Evidence

- SearXNG container and JSON endpoint: operational on localhost.
- X: no accepted record in final low-volume run; upstream rate-limit/CAPTCHA telemetry preserved.
- Threads: no accepted record in final low-volume run; upstream rate-limit/CAPTCHA telemetry
  preserved.
- Reddit: two real public records accepted end to end in the earlier low-volume run; final rerun
  was externally blocked.
- Bluesky, YouTube, Mastodon, GitHub, and Hacker News independently passed source verification;
  direct/public connectors remain first-class and were not replaced.
- RSS and GDELT remained configured supplemental sources.

## Known Limitations

- Credential-free web-index coverage depends on external search-engine indexing, snippet quality,
  rate limits, and CAPTCHA policy. It is neither complete nor real-time platform coverage.
- Indexed snippets may be stale or incomplete; discovery memory proves only that MIRSAD observed a
  public indexed URL.
- The local SearXNG instance cannot make an upstream engine available when that engine blocks the
  host environment. MIRSAD intentionally does not rotate proxies or solve CAPTCHAs.
- Official embed enrichment is platform-dependent and disabled by default; it does not provide
  missing public engagement metrics.
- Common Crawl Phase 1 lookup is exact-URL capture metadata, not historical keyword search across
  social platforms.
- X and Threads did not produce a live accepted record in the final environment; their internal
  paths are deterministically verified but current live availability remains externally limited.

MAFER FOUNDATION READY FOR INTELLIGENCE PHASE
