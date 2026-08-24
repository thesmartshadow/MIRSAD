# MIRSAD v1.2 Primary-Source Research

Recorded before v1.2 implementation on 2026-08-21. These sources define connector and local-index capabilities; they are not source-quality or truth assessments.

| Official source | Capability studied | Limitation | MIRSAD decision |
| --- | --- | --- | --- |
| [SQLite FTS5](https://sqlite.org/fts5.html) | `MATCH`, phrase/prefix queries, BM25, `rank`, `highlight()` and `snippet()` | Query punctuation is syntax-sensitive and retrieved markup is unsafe unless parsed | Keep parameterized FTS5 as the bounded lexical first stage. Preserve literal identifiers through safe FTS quoting and return structured highlights, never executable HTML. |
| [SQLite query planner](https://sqlite.org/queryplanner.html) | Multi-column indexes, row lookup, planner inspection | An index only helps when it matches the actual predicate/order | Require `EXPLAIN QUERY PLAN` evidence before adding indexes. No database migration away from SQLite. |
| [YouTube Data API: search.list](https://developers.google.com/youtube/v3/docs/search/list) | Query, language, publication bounds, type filter, page tokens, up to 50 records per request | Search has quota cost and bounded pagination | Retain bounded direct-API requests and explicit time/language variants; adaptive utility may reduce zero-yield work only in shadow until recall gates pass. |
| [GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) | Authenticated and unauthenticated limits, rate-limit response fields | Search has distinct rate behavior and temporary limits are not long-term utility evidence | Keep current health/rate-limit state separate from learned retrieval utility. Preserve identifiers, repository names, and commit hashes literally. |
| [Bluesky AppView endpoint reference](https://docs.bsky.app/docs/api/app-bsky-feed-search-posts) | `app.bsky.feed.searchPosts`, query, author, domain, language, tags, time bounds, cursor | Public availability and cursor behavior are externally controlled; cursor traversal is not an exhaustive corpus guarantee | Keep bounded public AppView acquisition. A live external limit does not erase historical utility or local-memory Bluesky evidence. |
| [Mastodon search](https://docs.joinmastodon.org/methods/search/) | Account, hashtag, URL and status search | Status full-text depends on instance search configuration and authentication | Model Mastodon as instance-scoped capability, not global coverage. Prefer literal handle/hashtag lanes and truthful `AUTH_REQUIRED`/no-capability states. |
| [Mastodon timelines](https://docs.joinmastodon.org/methods/timelines/) | Public and hashtag timelines with bounded pagination | Public access can be disabled or require authentication; results are instance-local | Keep public-timeline acquisition distinct from global search and report instance limitations as coverage gaps. |
| [GDELT DOC 2.0](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) | Full-text news discovery, phrases, Boolean query forms and temporal filtering | Time windows, language behavior, and response latency are service-defined | Retain bounded news retrieval and explicit timeout/external-limit coverage. Never trade away healthy-source evidence to wait indefinitely for GDELT. |
| [Common Crawl Index Server](https://index.commoncrawl.org/) | CDX index lookup by known URL patterns and crawl metadata | It is an index, not permission for arbitrary target crawling; bulk load must be bounded | Keep Common Crawl secondary and host/classifier bounded. Use it for known canonical historical discovery only; do not add a crawler. |
| [SearXNG Search API](https://docs.searxng.org/dev/search_api.html) | Optional engine selection, formats, categories and time ranges | Formats must be enabled and individual engines have different capabilities/external blocks | Keep SearXNG optional and disabled in the observed configuration. X/Threads/Reddit remain `WEB_DISCOVERY_DISABLED`, not failed direct connectors. |

## Applied constraints

- Routing learns retrieval yield and cost, never credibility or factual truth.
- Current source health is evaluated separately from historical utility.
- Local retrieval uses exact/FTS narrowing and bounded semantic opportunity; it does not scan the corpus semantically.
- Historical timestamps preserve publication, first observation, last observation, and external retrieval as separate facts.
- Phase 3 routing remains shadow-only unless deterministic per-intent holdout gates pass.

