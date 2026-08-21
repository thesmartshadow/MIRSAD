# Connectors

## Contract

Every connector subclasses `BaseConnector` and implements metadata, configuration validation, health check, asynchronous search, and payload normalization. Metadata exposes taxonomy, support level, coverage, credential/approval requirements, acquisition modes, and boolean/conditional search capabilities. `ConnectorItem` contains source/external ID, canonical URL, author name/handle/verification, title, untouched retrieved text, publication/fetch times, language, entities, media type, acquisition mode, raw metrics, and raw provenance metadata including `source_type`.

The common HTTP path enforces the connector base host, explicit timeouts, disabled redirects, at most two retries, bounded backoff/Retry-After, latency telemetry, JSON validation, and safe structured errors. RSS follows redirects only for feeds configured by the server and rejects payloads above 5 MB.

## Status And Error Taxonomy

Support, configuration, and runtime health are separate dimensions. The UI distinguishes `supported`, `supported_with_credentials`, and `restricted_access`; `configured`, `unconfigured`, and `restricted`; and `healthy`, `degraded`, `unavailable`, `access_limited`, `quota_exhausted`, or `rate_limited`. A connector class is not proof that platform access is configured or operational.

| Category | Meaning |
| --- | --- |
| `timeout` | The bounded request deadline expired. |
| `dns_network` | DNS, connection, TLS, or other network transport failed. |
| `http_401` | Upstream authentication was rejected. |
| `http_403` | Upstream access is unavailable from this environment. |
| `http_404` | The fixed upstream endpoint was not found. |
| `rate_limited` | HTTP 429; retry is bounded and the source remains explicit. |
| `quota_exhausted` | The configured quota or paid allowance is exhausted. |
| `access_limited` | Credentials exist but the current access tier/permission does not allow the request. |
| `restricted_access` / `capability_restricted` | The official API does not provide the requested global discovery capability under configured access. |
| `invalid_credentials` | An OAuth/token exchange did not produce usable authorization. |
| `upstream_5xx` | Temporary upstream server failure. |
| `invalid_payload` | JSON/XML structure or normalized records were invalid. |
| `auth_required` | A configured Mastodon instance has disabled unauthenticated public preview. |
| `unconfigured` | Required credentials or server configuration are absent. |
| `disabled` | The local operator disabled the source. |
| `connector_error` | An isolated implementation failure with no stack trace exposed. |

A failed connector never fails independent sources. A GitHub sub-scope failure reports a degraded warning while retaining records from successful scopes.

## Capability Matrix

| Group / source | Support | Actual official-API scope |
| --- | --- | --- |
| Social / X | Optional credentials or local SearXNG | Official recent/archive search when authorized. Otherwise validated indexed public post URLs with `WEB_INDEX` provenance; no X API capability is claimed for that mode. |
| Social / Threads | Optional credentials or local SearXNG | Official keyword/topic-tag search when authorized. Otherwise validated indexed public post URLs with `WEB_INDEX` provenance; no Threads API capability is claimed for that mode. |
| Social / Telegram | Credentials and authorized local session | `channels.searchPosts` public-channel keyword/hashtag search only. Results are rechecked for public broadcast username; private conversations are discarded. Search may be flood/paid-access controlled by Telegram. |
| Social / Reddit | Optional approved OAuth or local SearXNG | Approved API post search when configured. Otherwise validated indexed public post/comment URLs with `WEB_INDEX` provenance; no Reddit Data API capability or scraping is used. |
| Social / YouTube | API key and quota | Videos, channels, and playlists with keyword/language/region/date/sort; public video statistics are fetched in one batched call. Search pagination is capped at two quota-bearing pages. |
| Social / Bluesky | Public endpoint | Credential-free AppView post search uses `https://api.bsky.app` first and the fixed `https://public.api.bsky.app` secondary only after an eligible failure. Health checks call the actual search method. |
| Social / Mastodon | Public instance list; optional instance URL and user token | Authenticated `/api/v2/search` is preferred when configured. Otherwise MIRSAD concurrently fetches bounded recent public timelines, or a public hashtag timeline for hashtag intent, then filters locally. Coverage is instance-scoped, not global Fediverse search. |
| Social / Instagram | Approved Meta professional-account access | Hashtag discovery and recent hashtagged public media only. Generic global keyword search returns a capability restriction. |
| Social / TikTok | Research API approval and credentials | Approved Research API public-video queries in a bounded 30-day request window with public metrics and pagination. No scraping fallback. |
| Social / Facebook | Restricted | The adapter reports that global public-post keyword search is unavailable under configured ordinary Graph API access. It performs no network search. |
| Social / LinkedIn | Restricted | The adapter reports authorized user/organization scope only and no global public-post search. It performs no browser scraping. |
| News / GDELT | Public endpoint | DOC 2.0 article search, JSON list mode, bounded date range, at most 25 records, and a strict three-second total interactive budget. Attempts use a 1.25-second deadline, one bounded retry/backoff, and a temporary circuit breaker after repeated timeouts. |
| News / RSS | Server configuration | RSS/Atom feeds from `MIRSAD_RSS_FEEDS`; 5 MB cap and lexical post-fetch filtering. Telemetry separates fetched, schema-valid, query-matching, time-eligible, malformed, and normalized counts. It is not a general web crawler. |
| Developer / GitHub | Optional token | Repositories plus optional issues and pull requests; source code search is deliberately excluded. |
| Developer / Hacker News | Public endpoint | Algolia-backed public story/comment search. |
| Developer / mock | Explicit test/demo mode | Stable query-specific fixtures only; never a live-failure fallback. |

All credentials and session material remain backend-only. The metadata API publishes `configured`, `not configured`, `restricted`, or safe runtime errors but never token values.

## MAFER Web Discovery

The shared `WebSocialDiscoveryService` generates bounded `site:`-constrained queries for X, Threads, and Reddit, but does not trust the operator. Every result is reparsed against an exact host allowlist and platform-specific public-content pattern. Tracking parameters and known domain aliases are canonicalized; profiles, communities, home, search, login, malformed, credential-bearing, IP, non-HTTP, and wrong-domain URLs do not enter the post-result path.

SearXNG telemetry records engine, variant, target platform, latency, returned hits, target-domain hits, accepted canonical URLs, duplicates, timeout, rate-limit, and error. Multiple engines finding one canonical URL create `Discovery Support`, which measures independent discovery paths only. It is not truth, credibility, or reliability and is not added as an unbounded relevance signal.

Optional oEmbed calls occur only after URL validation, use fixed official endpoints, do not execute or persist embed HTML, and never fabricate engagement or timestamps. Optional Common Crawl mode accepts an exact validated URL and retrieves only bounded capture metadata from the current index; ordinary interactive keyword searches never invoke it.

## Adaptive Resource And Engine Routing

Automatic source selection is derived from connector capabilities and the deterministic query intent,
not a platform-name switch inside ranking. Resource utility exposes capability, intent, language,
temporal, historical yield, unique yield, latency, duplicate, novelty, and current-availability
components. Long-term utility and current availability are deliberately separate. Explicit user source
selection overrides automatic routing.

SearXNG engine state is `HEALTHY`, `DEGRADED`, `RATE_LIMITED`, `CAPTCHA_BLOCKED`, or
`TEMPORARILY_UNAVAILABLE`. Timeouts, 429s, and CAPTCHA responses open bounded cooldowns; a later
successful probe recovers the engine. Persistent observations measure discovery yield and cost only,
never truth or source credibility. Raw engine result scores are not compared. Canonical discoveries
are prioritized with weighted reciprocal-rank fusion using result rank, variant confidence, and a
bounded engine factor.

## Access And Live Verification

Run `npm run verify-sources` for the lowest-cost implemented credential/access checks. Optional unconfigured or restricted sources are `WARN`, rejected configured access is `FAIL`, and only an internal verifier failure causes a non-zero exit. The JSON artifact never contains secrets. See `docs/social-credentials.md` for the exact per-connector behavior.

Run:

```bash
npm run verify:live
```

The workflow probes `climate policy`, `open data`, and `العراق`, measures configuration, status, HTTP status, latency, fetched/normalized/malformed counts, timeout/retry policy, and safe error category, then writes versioned JSON and Markdown in `reports`. It is supplemental because public platform behavior is time- and environment-dependent.

## Adding A Connector

1. Implement the entire contract with a fixed host and bounded network behavior.
2. Preserve original content, identifiers, URLs, subtype, and raw metrics.
3. Add a platform-relative engagement adapter.
4. Register safe metadata without exposing credentials.
5. Add normalization, invalid-payload, timeout/rate-limit, failure-isolation, and API tests.
6. Update this document and the live verifier when appropriate.
