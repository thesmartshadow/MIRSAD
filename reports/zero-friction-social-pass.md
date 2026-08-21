# Zero-Friction Social Sources Pass

Generated: 2026-08-09 (Asia/Baghdad)

## Scope

This pass changed connector operations only. The frozen lexical admission,
top-20 MiniLM reranking, 25/75 relevance fusion, one-percent secondary quality
budget, deduplication, and hardened story clustering were not changed.

## Implemented

- Bluesky public search now uses `https://api.bsky.app` as the primary fixed
  AppView origin and `https://public.api.bsky.app` as a one-way fallback after
  eligible primary failures. No account or token is required.
- Bluesky health verification calls `app.bsky.feed.searchPosts` with one harmless
  result rather than probing the origin root.
- A later Bluesky page failure no longer discards an earlier successful page. The
  connector returns the real earlier records with an explicit partial warning.
- Mastodon retains authenticated `/api/v2/search`, but automatically uses bounded
  credential-free public timeline filtering when no token is configured. Hashtag
  intent uses `/api/v1/timelines/tag/:hashtag`.
- Mastodon instances come only from server-side configuration. Up to four valid
  HTTPS origins are queried concurrently with bounded per-instance requests,
  isolated failures, federated URL deduplication, and instance provenance.
- Connector metadata now declares public timeline, hashtag timeline,
  authenticated full-text, and instance-scoped capabilities. The UI describes
  the source as public timeline coverage, not global Mastodon search.
- Search diagnostics preserve and display collection mode, instances, fetched,
  valid, local matching, normalized, malformed, and federated duplicate counts.
- YouTube Sources-page health now uses the same low-cost credential probe as
  `verify-sources`, eliminating a misleading `unknown` state after refresh.

## Configuration

The tested local configuration had a YouTube API key, no Mastodon user token, and
one public instance (`https://mas.to`). Bluesky required no credential. No secret
value was printed, written to this report, returned by the API, or placed in the
frontend bundle.

## Live Verification

Final `npm run verify-sources` evidence:

| Source | State | Validation | Latency |
| --- | --- | --- | ---: |
| YouTube | PASS | API key accepted by YouTube Data API | 438 ms |
| Bluesky | PASS | Public AppView search available | 879 ms |
| Mastodon | PASS | Public timeline mode; full-text search not configured | 352 ms |

Low-volume real collection probes:

| Source / query | HTTP | Fetched | Valid | Matching | Normalized/returned | Latency | Mode |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Bluesky / `بغداد` | 200 | 20 | 20 | 20 | 20 | 1,218 ms | Public AppView |
| Mastodon / `technology` | 200 | 40 | 40 | 0 | 0 | 374 ms | Public timeline filtering |
| Mastodon / `#technology` | 200 | 40 | 40 | 40 | 20 | 655 ms | Hashtag timeline |
| YouTube / `technology` | 200 | 5 | 5 | 5 | 5 | 1,230 ms | Data API search |

The zero-result Mastodon keyword probe is valid: 40 recent public statuses were
schema-valid, but none matched both local query tokens. It was not reported as 40
search results.

The real `#technology` unified API session queried all three sources concurrently
and returned HTTP 201 in 2.47 seconds. Connector collection took 1.27 seconds:

| Source | Fetched | Valid | Connector matches | Common-pipeline matches | Collected |
| --- | ---: | ---: | ---: | ---: | ---: |
| YouTube | 30 | 30 | 30 | 8 | 8 |
| Bluesky | 30 | 30 | 30 | 30 | 0 |
| Mastodon | 40 | 40 | 40 | 30 | 22 |

The frozen global 30-record candidate cap selected 22 Mastodon and 8 YouTube
records for that session; it was not changed in this connector-only pass. The
session completed without warnings, persisted 30 unique records, and created 28
story clusters.

## Bluesky Pagination Observation

During a later Arabic API search, Bluesky returned page one with HTTP 200 and 17
real records, then returned HTTP 403 for the cursor request. The secondary origin
also returned 403 for that cursor. MIRSAD did not retry the forbidden primary and
did not discard page one: it normalized 17, admitted/persisted 13, retained 12
unique records, and returned the session as partial with the exact warning. Total
session time was 2.83 seconds; semantic reranking used the unchanged local MiniLM
strategy and took 817 ms.

This is an observed upstream cursor restriction, not an authentication bypass.
The one-result health request and ordinary first page remain available.

## UI And Export

The live Arabic Bluesky session rendered 13 external result links. Browser
automation opened its diagnostics, displayed `PUBLIC APPVIEW SEARCH`, switched
English to Arabic and back, retained all 13 results, observed correct
`html[lang][dir]`, displayed Mastodon instance-scoped coverage, and recorded no
console errors.

JSON and CSV export both returned HTTP 200 for the live Arabic session. JSON used
the versioned `mirsad.search-export` schema and contained 13 records with original
Bluesky URLs. CSV contained a UTF-8 BOM and intact Arabic text.

## Validation

- Backend: 135 passed.
- Frontend: 14 passed across 6 files.
- Playwright: 11 passed, 2 opt-in live-fixture cases skipped; the separate live
  browser smoke passed with no console errors.
- Ruff, Oxlint, TypeScript, and Vite production build: passed.
- Doctor: all checks passed.
- `verify-sources`: exited zero; all three pilot sources passed.
- SQLite: `integrity_check=ok`, no foreign-key violations, 215 content rows and
  215 FTS rows. Insert/update/delete FTS trigger lifecycle is covered by the
  passing database suite.
- Startup: API and frontend reached readiness on localhost; foreground services
  supported the live HTTP/browser workflow.

## Coverage Limits

- Mastodon public mode sees only recent public posts known to configured
  instances. It is not global Fediverse full-text search.
- A Mastodon instance can legitimately disable public preview; MIRSAD reports
  `AUTH_REQUIRED` without treating that policy as an implementation defect.
- Bluesky AppView search is credential-free, but cursor requests can be
  independently forbidden. Earlier successful pages remain usable and the partial
  state is explicit.
- YouTube remains subject to the configured project quota.
