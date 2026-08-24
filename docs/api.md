# API

The REST API is versioned under `/api/v1`. FastAPI serves interactive documentation at `/docs` and OpenAPI at `/api/v1/openapi.json`. Typed Pydantic responses and the generic exception handler prevent stack traces from reaching clients.

## Search, Diagnostics, And History

`POST /api/v1/searches` runs a concurrent persisted search:

```json
{
  "query": "public policy",
  "sources": ["hacker_news", "github", "rss"],
  "time_range": "7d",
  "language": "all",
  "limit": 50,
  "search_mode": "balanced",
  "source_selection": "auto",
  "exact_phrase": false,
  "sort": "best_match",
  "content_types": ["posts", "videos"],
  "has_media": null,
  "has_links": null,
  "hashtags": [],
  "source_options": {
    "threads": {"mode": "keyword", "sort": "recent"},
    "reddit": {"communities": ["iraq"]},
    "youtube": {"types": ["video", "channel"], "region": "IQ"}
  }
}
```

Sort values are `best_match`, `newest`, `most_engaged`, and `cross_platform`. Search modes are `fast`, `balanced`, and `deep`; they are bounded effort profiles, not completeness claims. `source_selection=auto` enables capability/intent routing, while `explicit` preserves the supplied source set. A partial search returns HTTP 201, successful results, status `partial`, and safe connector warnings. Result records include `acquisition_mode` (original ingestion), `acquisition_modes_seen`, `acquisition_path` and `acquisition_paths` (how this execution obtained the candidate), `indexed_public_web_coverage`, `discovery_support`, `discovery_engines`, and `evidence_completeness`. A result may therefore have `platform=bluesky` and `acquisition_path=LOCAL_MEMORY` without implying that the live Bluesky connector executed.

For responsive clients, `POST /api/v1/search/jobs` accepts the same request and returns HTTP 202 with
`job_id`, the reserved `session_id`, and status `started`. Consume
`GET /api/v1/search/jobs/{job_id}/events` as `text/event-stream`, then read the authoritative persisted
response from `/api/v1/searches/{session_id}` after `search.completed` or `search.partial`. Event names are:

- `search.started`, `planning.started`, `planning.completed`
- `acquisition.local_memory.started`, `acquisition.local_memory.completed`
- `source.selected`, `source.started`, `source.progress`, `source.completed`, `source.degraded`, `source.failed`, `source.skipped`
- `collection.progress`, `normalization.completed`, `persistence.completed`
- `semantic.preparation.started`, `semantic.preparation.completed`
- `ranking.started`, `ranking.completed`, `clustering.started`, `clustering.completed`
- `search.partial`, `search.completed`, `search.failed`

Events contain only bounded counts, source keys, safe failure categories, elapsed times, and opaque job/session
identifiers. They never contain credentials or raw exception dumps. Preliminary counts are progress telemetry,
not ranked results. Jobs, retained events, and TTL are bounded; disconnecting the stream does not corrupt a
persisted search. The synchronous endpoint remains supported.

- `GET /api/v1/searches?limit=50&offset=0`: paginated summaries.
- `GET /api/v1/searches/{session_id}`: stored results, explanations, clusters, and analytics.
- `GET /api/v1/searches/{session_id}/diagnostics`: stored query, MAFER intent/lattice/resource plan/rounds/budget/uncertainty/gain/stop trace, connector completion order, live connector funnels, platform-plus-acquisition funnels, semantic-preparation/cache state, per-engine web-discovery telemetry, phase, duplicate, and score-distribution diagnostics. Local-memory rows always report zero network requests.
- `GET /api/v1/searches/{session_id}/coverage`: persisted coverage read model. It keeps search outcome separate from coverage, reports LIVE, LOCAL_MEMORY, and HISTORICAL lanes, and classifies each source as executed, skipped, unavailable, externally limited, restricted, unconfigured, no-match, or web-discovery-disabled. It never invents a percentage denominator.
- `GET /api/v1/searches/{session_id}/export?format=csv|json`: direct download; no filesystem path is accepted.

Search responses also include the same typed `coverage` object so the completed workspace can render without recomputing planner evidence. Current connector health and long-term shadow utility remain separate. Adaptive recommendations are diagnostic only and never alter the production Phase 2 plan.

JSON exports use schema `mirsad.search-export`, version `1.0`, and contain generated time, session/filter metadata, analytics, acquisition/discovery provenance, and records. CSV includes the same acquisition/discovery fields, is UTF-8 with BOM for Arabic interoperability, and prevents formula-like content from being interpreted by spreadsheets.

## Analytics, Clusters, And Compare

- `GET /api/v1/analytics?scope=all|24h|7d|30d`: persisted content analytics for an explicit scope. `all` is the default. Content/canonical counts are distinct from search-result appearances so repeated session links do not inflate the stored corpus.
- `GET /api/v1/analytics/{session_id}`: analytics for exactly one stored search session, including its query and collection time in the scope metadata.
- `GET /api/v1/clusters?session_id={id}`: clusters with member public IDs.
- `POST /api/v1/compare`: accepts `left_session_id` and `right_session_id`, returns both summaries/snapshots, and flags materially different collection windows.
- `GET /api/v1/duplicate-groups/{id}?sort=newest|source|engagement`: representative, members, source/time distribution, similarity, and match stage.

## Saved Searches

- `GET /api/v1/saved-searches`
- `POST /api/v1/saved-searches` with `{ "name": "...", "configuration": {SearchRequest} }`
- `PATCH /api/v1/saved-searches/{id}` to rename
- `POST /api/v1/saved-searches/{id}/duplicate`
- `POST /api/v1/saved-searches/{id}/run`
- `DELETE /api/v1/saved-searches/{id}`

Saved searches are local configurations only; there is no scheduler or monitoring worker.

## Bookmarks

- `GET /api/v1/bookmarks`
- `POST /api/v1/bookmarks` with content ID, optional discovery session ID, and note
- `PATCH /api/v1/bookmarks/{id}` to update the note
- `DELETE /api/v1/bookmarks/{id}`

Content references are unique. Notes are limited to 1,000 characters and never modify retrieved content.

## Sources

- `GET /api/v1/sources`: safe configuration, capability metadata, taxonomy, support/coverage level, and health telemetry.
- `POST /api/v1/sources/health`: configuration-level refresh without pretending a live query ran.
- `PATCH /api/v1/sources/{source_key}`: allowlisted `enabled`, `confidence`, and GitHub `github_scopes` values.

Responses expose no token/key/session values. They report only safe states such as configured, unconfigured, restricted, invalid credentials, access limited, quota exhausted, rate limited, unavailable, degraded, or healthy. GitHub scope values are `repositories`, `issues`, and `pull_requests`.

## Settings, Data, And System

- `GET /api/v1/settings`: client-safe settings only.
- `PUT /api/v1/settings`: update allowlisted safe values; invalid weights/unknown keys return 422.
- `POST /api/v1/settings/reset`: safe defaults.
- `GET /api/v1/data/counts`: local record counts.
- `POST /api/v1/data/actions/{action}` with `{ "confirm": true }`: one of `clear_history`, `clear_bookmarks`, `clear_cache`, `rebuild_fts`, or `reset_database`.
- `POST /api/v1/data/manual-import`: import one validated public X/Threads post or Reddit post/comment URL plus operator-selected visible text. It performs no page fetch and records `MANUAL_IMPORT` provenance.
- `GET /api/v1/health`: lightweight liveness.
- `GET /api/v1/system`: API/database/FTS/source state, record/index counts, integrity result, FK violations, capabilities, and version.
- `GET /api/v1/quality`: observed local outcomes, query/language distributions, production stop and uncertainty counts, bounded shadow source/engine utility, shadow comparison counts, and active configuration snapshots. It does not infer precision without judgments.
- `POST /api/v1/quality/events`: record a bounded local `RESULT_OPENED`, explicit relevance judgment, or reformulation event. Result ownership, rank, source, acquisition mode, query class, and algorithm versions are resolved server-side.
- `POST /api/v1/quality/configuration/initialize`: idempotently ensure verified and experimental configuration slots exist.
- `POST /api/v1/quality/rollback`: confirmed one-step algorithm-configuration rollback. It does not alter stored content.

## Limits And Headers

- Body maximum: 64 KiB.
- Query: `1..300` characters containing at least one Unicode letter or number after trimming.
- Results: `1..200`.
- Sources: `1..30`, deduplicated.
- Bookmark note: at most 1,000 characters.
- Validation: HTTP 422; missing resource: 404; duplicate bookmark: 409.
- External failures: safe structured warnings in partial searches.
- Unexpected errors: HTTP 500 with `{ "detail": "Internal server error" }`.

Responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a restrictive `Permissions-Policy`.
