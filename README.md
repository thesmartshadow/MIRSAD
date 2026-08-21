# MIRSAD

MIRSAD is a local-first public content discovery and analysis system for institutional research. It concurrently collects public records, normalizes them into one provenance-preserving model, indexes text with SQLite FTS5, applies explainable relevance-first ranking with optional local multilingual reranking, preserves duplicate groups, creates bounded explainable story clusters, and presents stored analytics in an Arabic/English dashboard.

MIRSAD does not assign truth scores. Source Confidence is an editable ranking preference, and Cross-Source Presence measures distribution rather than factual verification. No content is sent to an external LLM.

## Capabilities

- Search from a responsive analyst workspace with source, time, language, limit, exact-phrase, and sort controls.
- Observe bounded real-time planning, per-source acquisition, ranking, and clustering progress while the final deterministic result order remains authoritative.
- Select capability-driven source presets for Social Media, News, Developer & Community, All Sources, or a custom set.
- Inspect score components, duplicate groups, clusters, connector telemetry, and per-session search diagnostics.
- Persist and reopen history, saved search configurations, bookmarks, and bookmark notes locally.
- Export stored sessions as UTF-8 CSV or versioned JSON and open a print-friendly report for browser Print / Save as PDF.
- Compare stored searches while displaying collection-window differences.
- View Analytics over all persisted content by default, or explicitly scope it to one search session or a recent time window; stored content and session appearances are reported separately.
- Use complete English LTR and Arabic RTL navigation, forms, results, analytics, dialogs, and settings.
- Perform confirmed data actions independently: clear history, bookmarks, or cache; rebuild FTS; or reset local data.
- Optionally discover validated public X, Threads, and Reddit content URLs through a locally operated SearXNG instance, with web-index provenance kept distinct from direct platform APIs.
- Use deterministic MAFER intent analysis, bounded query variants, capability-aware automatic source routing, local-memory round zero, and Fast/Balanced/Deep retrieval budgets before the unchanged final ranker.
- Record optional local relevance judgments and evaluate adaptive alternatives in shadow mode while keeping the verified Phase 2 planner authoritative.
- Capture an operator-selected public X, Threads, or Reddit URL and visible text through the optional localhost-only browser companion when web indexes are externally blocked.

## Architecture

- `apps/web`: React 19, TypeScript, Vite, Tailwind CSS, and shadcn/ui. Recharts is used only through shadcn Chart composition.
- `apps/api`: FastAPI, Pydantic, SQLAlchemy, `httpx`, and `asyncio` connector orchestration.
- `data/mirsad.db`: local SQLite database with FTS5 and insert/update/delete synchronization triggers.
- `infra/searxng`: optional localhost-only SearXNG deployment for credential-free public web discovery.
- `reports`: reproducible search-quality, performance, and supplemental live-source reports.

Backend connector, query, ranking, engagement, deduplication, clustering, analytics, persistence, export, configuration, and health responsibilities remain separate modules.

Search jobs are an optional transport around the existing synchronous search service. The frontend starts
a bounded expiring job, consumes safe typed server-sent events, and reads the persisted SearchSession only
after a terminal event. A disconnected browser does not roll back or corrupt the session, and retained job
events are capped. Existing API consumers may continue using `POST /api/v1/searches`.

## Sources

| Group | Source | Configuration | Actual discovery scope |
| --- | --- | --- | --- |
| Social | X | Optional `X_BEARER_TOKEN`; otherwise local SearXNG | Official recent post search when authorized. Without a token, MIRSAD validates indexed public post URLs; this is not X API search. |
| Social | Threads | Optional `THREADS_ACCESS_TOKEN`; otherwise local SearXNG | Official search where authorized. Without a token, MIRSAD validates indexed public post URLs; this is not Threads API search. |
| Social | Telegram | API ID/hash plus local authorized session | Public channel posts only through Telegram's documented API; never private chats. |
| Social | Reddit | Optional approved OAuth credentials; otherwise local SearXNG | Approved API search when configured. Without credentials, MIRSAD validates indexed public post/comment URLs; this is not Reddit Data API search. |
| Social | YouTube | `YOUTUBE_API_KEY` | Public videos, channels, playlists, and video statistics with bounded quota use. |
| Social | Bluesky | No credential | Public AppView post search through `api.bsky.app`, with a fixed secondary endpoint. |
| Social | Mastodon | No credential for public mode; optional instance token | Bounded recent public/hashtag timeline filtering on server-configured instances; authenticated full-text search is preferred when configured. |
| Social | Instagram | Approved professional-account Meta access | Hashtagged public media only; no unrestricted global keyword search. |
| Social | TikTok | Approved Research API credentials | Public video research queries; approval is mandatory. |
| Social | Facebook | Restricted adapter | No unrestricted global public-post search under ordinary configured Graph API access. |
| Social | LinkedIn | Restricted adapter | Authorized user/organization APIs only; no global public-post search. |
| News | GDELT | No credential | DOC 2.0 article search with a 25-record cap, a three-second total interactive budget, and a temporary circuit breaker after repeated timeouts. |
| News | RSS | Server-configured | RSS/Atom feeds listed only in `MIRSAD_RSS_FEEDS`. |
| Developer / Community | GitHub | Optional `GITHUB_TOKEN` | Repositories by default; issues and pull requests are selectable. Source code is excluded. |
| Developer / Community | Hacker News | No credential | Public Algolia-backed story/comment search. |
| Developer / Community | Deterministic mock | Explicit test/demo mode | Never used as fallback for a live failure. |

Availability depends on platform policies, quotas, credentials, network routing, and the query. See [connector documentation](docs/connectors.md) and the timestamped [live report](reports/live-connectors.md).

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and npm
- SQLite compiled with FTS5

## Install And Run

```bash
cp .env.example .env
npm run install:all
npm run doctor
./start.sh
```

The core application runs with deterministic lexical ranking. To install the selected optional local
multilingual reranker and its model files, run `npm run install:semantic`. The model is used only from
local storage, reranks at most 20 lexical candidates, and falls back to lexical ranking if unavailable.

Open `http://127.0.0.1:5173`. API documentation is at `http://127.0.0.1:8000/docs`. Logs and PIDs are in `.run`; stop both services with `./stop.sh`.

For foreground development with Vite/FastAPI reload behavior, use `npm run dev`. Services can also run separately with `npm run dev:web` and `npm run dev:api`.

Optional backend-only credentials stay in `.env`:

```dotenv
GITHUB_TOKEN=
YOUTUBE_API_KEY=
X_BEARER_TOKEN=
THREADS_ACCESS_TOKEN=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_STRING=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
MASTODON_BASE_URL=
MASTODON_ACCESS_TOKEN=
MASTODON_PUBLIC_INSTANCES=https://mas.to
MIRSAD_MASTODON_PUBLIC_PAGES=1
MIRSAD_MASTODON_PUBLIC_RECORDS_PER_INSTANCE=40
MIRSAD_MASTODON_INSTANCE_CONCURRENCY=3
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_USER_ID=
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
MIRSAD_TIKTOK_RESEARCH_APPROVED=false
MIRSAD_GITHUB_SCOPES=repositories
MIRSAD_RSS_FEEDS=https://feeds.bbci.co.uk/news/world/rss.xml
MIRSAD_SEARCH_JOB_TTL_SECONDS=900
MIRSAD_SEARCH_JOB_MAX_ENTRIES=32
MIRSAD_SEARCH_JOB_EVENT_LIMIT=128
```

Use `repositories,issues,pull_requests` to enable all supported GitHub scopes. Secrets are never returned by the API or stored in client-safe settings. The exact fields, authorization models, refresh behavior, and implemented validation requests are documented in [social connector credentials](docs/social-credentials.md).

### Optional MAFER Web Discovery

Enable the bundled local SearXNG service in `.env`; `./start.sh` starts it, waits for its bounded JSON
readiness probe, and leaves direct/public sources available if upstream engines are externally blocked:

```bash
SEARXNG_ENABLED=true
SEARXNG_URL=http://127.0.0.1:8080
```

The backend generates bounded domain-constrained queries, independently validates every returned URL, rejects navigation/profile results from the post path, and stores acquisition and engine provenance. SearXNG upstream failures remain visible and isolated. No CAPTCHA solving, proxy rotation, login automation, or paid engine is configured. Optional Common Crawl lookup accepts only an already validated public post/comment URL and returns capture metadata; it is never run for ordinary keyword searches.

When every web-index engine is externally blocked, the optional unpacked companion in
`tools/browser-capture` imports only the active public URL, title, and operator-selected visible text.
The backend never fetches that page and rejects profiles, unsafe hosts, and non-content URLs.

### Adaptive Federated Planning

When source selection is Automatic, MAFER classifies the query with inspectable rules, preserves the
original text, creates at most the selected budget's number of conservative variants, checks local
content/discovery memory, and routes sources from connector capability metadata. Current health and
long-term retrieval utility are separate, so a temporary CAPTCHA or rate limit suppresses immediate
requests without teaching MIRSAD that the target platform is intrinsically unhelpful.

`Fast`, `Balanced` (default), and `Deep` enforce different wall-clock, round, request, discovery URL,
candidate, and historical-lookup limits. Each round records evidence gain and uncertainty, then stops
with an explicit reason. Deep permits wider work but does not continue when the available evidence no
longer justifies another round. Discovery-engine and query-variant ranks are combined by bounded
weighted reciprocal-rank fusion only to prioritize discovered URLs. The downstream FTS/MiniLM ranker
remains unchanged.

### Phase 3 Quality Evidence

MIRSAD records privacy-conscious local outcome events and optional explicit `Relevant` / `Not relevant`
judgments. Opening a result is recorded separately and is never interpreted as relevance. Retrieval
utility is time-decayed and bounded, requires minimum evidence, and currently affects only a shadow
router. Shadow uncertainty, stopping, query-aware fusion, Arabic-model, and near-tie diversity
experiments cannot change visible production results.

The System route displays observed local counts, explicit judgments, source/engine retrieval utility,
production stop/uncertainty distributions, and production-versus-shadow comparisons. It does not infer
live precision without judgments. Versioned configuration snapshots support a confirmed one-step
algorithm rollback without modifying stored content. See [MAFER Phase 3](docs/mafer-phase3.md).

## Validation

```bash
npm test
npm run lint
npm run typecheck
npm run build
npm --prefix apps/web exec playwright install chromium
npm run test:e2e
npm run evaluate:search
npm run evaluate:holdout
npm run evaluate:mafer
npm run evaluate:mafer-phase3
npm run evaluate:mafer-phase3-arabic
npm run evaluate:mafer-phase3-confidence
npm run evaluate:production-evidence
npm run smoke:production-live
npm run benchmark:relevance
npm run benchmark
npm run benchmark:evidence
npm run audit:mixed-source-cap
npm run verify-sources
```

The primary suites use deterministic fixtures and require no third-party network. Live verification is explicit and supplemental:

```bash
npm run verify:live
```

It sends three harmless English/Arabic queries to configured fixed endpoints and writes safe telemetry to `reports/live-connectors.json` and `.md`. It does not bypass access controls or convert failures into mock results.

`npm run verify-sources` performs low-cost credential/access checks, reports optional unconfigured connectors as warnings, and never prints secrets. `verify:live` is the separate query-through-normalization probe. RSS telemetry deliberately distinguishes records fetched from a configured feed, schema-valid feed entries, query-matching entries, and final normalized matches; a non-matching feed is not reported as a normalization failure.

## Operations

| Command | Purpose |
| --- | --- |
| `npm run doctor` | Report Python, Node, FTS5, directories, environment, dependencies, and database status as PASS/WARN/FAIL. |
| `npm run start` / `npm run stop` | Start or stop both localhost services in the background. |
| `npm run reset-db` | Recreate the configured local SQLite database and FTS schema. |
| `npm run evaluate:search` | Generate machine- and human-readable deterministic IR metrics. |
| `npm run evaluate:holdout` | Evaluate the unchanged ranker against the separate dense relevance holdout. |
| `npm run evaluate:relevance-recovery` | Reproduce the SHA-256 guarded final hybrid holdout evaluation; do not use it for tuning. |
| `npm run evaluate:mafer` | Run the separate deterministic search-planning benchmark and Phase 2 ablation study; it does not tune or invoke the frozen final relevance holdout. |
| `npm run evaluate:mafer-phase3` | Reproduce Phase 3 development calibration; the hash-guarded holdout remains an acceptance set, not a tuning input. |
| `npm run evaluate:mafer-phase3-arabic` | Reproduce the Arabic candidate-loss funnel. |
| `npm run evaluate:mafer-phase3-confidence` | Recompute paired confidence intervals from existing frozen Phase 3 artifacts without rerunning the holdout. |
| `npm run benchmark:relevance` | Measure cold/warm local reranking and lexical scaling without network time. |
| `npm run benchmark` | Measure representative concurrent local search phase timings. |
| `npm run benchmark:evidence` | Measure GDELT total-budget semantics, first-useful-result timing, and bounded backend memory observations. |
| `npm run audit:mixed-source-cap` | Audit 11 mixed Arabic/English/hashtag queries for per-source admission, score distributions, and completion-order invariance using the real FTS/MiniLM pipeline. |
| `npm run verify-sources` | Validate configured source access safely without running a full search where a cheaper check exists. |
| `npm run verify:live` | Run supplemental real-source probes. |
| `npm run evaluate:production-evidence` | Run the explicitly live, bounded real-record/known-item evaluator; it is not a CI command. |
| `npm run smoke:production-live` | Run eight bounded real automatic-routing searches into an isolated evidence database. |

The optional container flow preserves the normal local workflow:

```bash
docker compose --profile mafer up --build
docker compose down
```

Only localhost ports are published, and SQLite data persists in the `mirsad-data` volume.

## Limitations

- Live source behavior is not controlled by MIRSAD. Restricted, unconfigured, access-limited, quota-exhausted, rate-limited, and unavailable states remain visible rather than being bypassed or replaced with fixtures.
- Direct X, Threads, Telegram, Reddit, YouTube, Instagram, and TikTok APIs require platform credentials and/or approval. X, Threads, and Reddit can additionally use local web-index discovery when SearXNG is enabled, but indexed snippets may be incomplete or stale and are never represented as direct platform API records. Mastodon public-timeline mode and Bluesky AppView search do not require credentials. Facebook and LinkedIn adapters intentionally do not claim global public-post discovery.
- Telegram coverage is public channels only, Mastodon coverage is limited to public posts known to configured instances, and Instagram coverage is hashtag-only.
- Anonymous GitHub requests have lower quotas. Optional issue/pull-request scopes increase request volume and may partially degrade while successful scopes still return records.
- RSS is lexical post-fetch filtering over operator-configured feeds; it is not a general web crawler.
- Optional semantic reranking improves ordering but is not a truth or reliability model; Arabic dense-collision quality remains weaker than English in the frozen holdout.
- Phase 3 adaptive routing/stopping, query-aware fusion, the larger Arabic shadow model, and near-tie diversity remain experimental because the independent holdout did not establish a conclusive production gain at the current sample size.
- Story clustering uses query-dampened rare-term/entity blocks, complete-linkage admission, temporal context, and the existing optional local multilingual model inside bounded candidate blocks. It favors precision and does not provide factual verification.
- Trend comparisons are descriptive and do not claim statistical significance.
- MIRSAD is a single-local-operator application without multi-user authentication or hosted deployment automation.

Further details: [architecture](docs/architecture.md), [data model](docs/data-model.md), [connectors](docs/connectors.md), [scoring](docs/scoring.md), [MAFER Phase 3](docs/mafer-phase3.md), [API](docs/api.md), and [acceptance](docs/acceptance.md). Current evidence is in the [release-readiness](reports/release-readiness.md), [live-pilot](reports/live-pilot.md), [deep-audit](reports/deep-audit.md), and [final intelligence review](reports/final-intelligence-review.md) reports.
