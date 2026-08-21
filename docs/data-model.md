# Data Model

SQLite initializes automatically at API startup. Foreign keys, WAL mode, a five-second busy timeout, indexes, and uniqueness constraints are enabled. Public identifiers use UUID strings while high-volume tables use internal integer keys.

The unified content row extends existing records with nullable `author_handle`, `author_verified`, `hashtags`, `mentions`, and `media_type` fields plus an explicit `acquisition_mode`. Metrics preserve source-specific JSON plus nullable columns for likes, views, comments, shares, reposts, and reactions. An unavailable upstream metric remains null/absent rather than being rewritten as zero.

## Tables

| Table | Purpose |
| --- | --- |
| `sources` | Connector identity, enablement/configuration, editable confidence, and non-secret public configuration. |
| `source_health` | Health/status category, HTTP status, last and average latency, request/failure counts, result/malformed counts, and last success/failure. |
| `connector_runs` | Session/source execution status, category, HTTP status, total/attempt latencies, attempt count, fetched/schema-valid/query-matching/time-eligible/final/normalized/malformed counts, circuit state, and timestamps. |
| `search_queries` | Original/normalized query, detected language, ordered/unique tokens, generated variant strings, and exact mode. Intent and per-variant reasons are retained in the session diagnostics snapshot rather than duplicated in this row. |
| `search_sessions` | Parameters, source set, warnings, status, counts, duration, timestamps, and diagnostics snapshot. |
| `content_items` | Unified source record, original title/text, provenance, source subtype, canonical URL, author, language, timestamps, and fingerprint. |
| `content_metrics` | Raw source metrics, normalized engagement, and adapter version. |
| `content_scores` | Per-session final score, every positive component, penalty, matched terms, and explanation. |
| `search_results` | Per-session content membership, rank, duplicate group, and cluster. |
| `duplicate_groups` | Representative item, source names/count, record count, and first/last observation. |
| `duplicate_group_members` | Preserved members, similarity, and matching stage. |
| `clusters` / `cluster_members` | Representative title, source/platform distribution, platform diversity, MIRSAD-observed time range, aggregate score, terms, members, and similarity. |
| `analytics` | Stored session-scoped analytics snapshots. |
| `saved_searches` | Named local search configurations; no schedule or background monitoring state. |
| `bookmarks` | Unique reference to a content item, optional discovery session, and a separate local note. |
| `response_cache` | Expiring local connector cache records; currently managed and clearable without exposing payloads to settings. |
| `discovery_records` | Canonical public URL memory: platform/type/stable ID, indexed title/snippet, acquisition, completeness, fingerprint, availability, and first/last seen by MIRSAD. |
| `discovery_observations` | Unique engine/query/variant support for a canonical discovery record. |
| `discovery_cache` | Bounded expiring SearXNG discovery responses keyed by normalized query, variants, platform, language, time scope, engine selection, limit, and historical flag. |
| `discovery_engine_stats` | Per-engine/platform observations separating current cooldown state from historical target-domain yield, unique yield, duplicate, latency, timeout, and rate-limit behavior. |
| `entity_alias_edges` | Conservative local name/handle/domain/profile relationships with evidence source, support count, first/last seen, and confidence; only repeated high-confidence edges may create a query variant. |
| `settings` | Allowlisted categorized client-safe preferences; no credentials. |
| `audit_events` | Important local operation events with non-secret structured context. |

`content_items` is unique on `(source_id, external_id)`. Repeated searches create new session results and scores while reusing the immutable retrieved content record. Bookmarks reference content and do not copy or mutate it. Deleting content cascades metrics/bookmarks; clearing history explicitly removes session analysis in dependency order and sets bookmark discovery sessions to null.

`discovery_records` is unique on canonical URL, so multiple engines and query variants add observations instead of duplicate content. Discovery memory is intentionally not inserted directly into `content_fts`; only a validated discovery that becomes a normalized `content_item` enters the authoritative content index. This prevents remembered profiles/navigation candidates and stale index snippets from contaminating ordinary FTS candidate retrieval.

## FTS5

`content_fts` is an external-content FTS5 table over original title, text, and author plus their normalized counterparts using `unicode61 remove_diacritics 2`. The original fields remain authoritative retrieved content; normalized fields exist only for lexical matching, including conservative Arabic variants. Insert, update, and delete triggers keep the index synchronized. Search uses bound MATCH expressions and normalizes BM25 strength as one relevance input.

SQLite has no native timezone-aware datetime storage. ORM datetime columns therefore use MIRSAD's `UTCDateTime` type: writes are normalized to UTC and reads are restored as aware UTC values. API serialization and exports retain an explicit UTC offset.

System diagnostics run `PRAGMA integrity_check` and `PRAGMA foreign_key_check`, compare content/index counts, and expose safe results. Tests verify FTS synchronization after insert, update, and deletion. `rebuild_fts` invokes FTS5 rebuild; reset recreates the schema and triggers.

## Group Relationships

Duplicate and cluster membership is additive. No original is removed because it matches another record. Duplicate member uniqueness is enforced within each group, as is cluster membership. Search result/score uniqueness is enforced per session/content pair.

Duplicate stages are canonical URL, normalized-content fingerprint, then near-text similarity. Cross-source metadata records distinct connector count/names, record count, and earliest/latest timestamps. Clusters are session-scoped story groups, not broad-topic buckets: query terms are dampened, duplicate groups contribute one identity representative, and semantic comparison is bounded to plausible rare-term/entity/temporal candidates. Platform diversity counts independent participating connectors, and first seen is labeled `First Seen by MIRSAD`. Neither implies truth, causality, actual origin, or exact identity.

## Data Actions

Settings > Data exposes separate confirmed actions:

- Clear history: removes search sessions and their analysis while retaining reusable content and bookmark references.
- Clear bookmarks: removes only bookmarks.
- Clear cached responses: removes response-cache and discovery-cache rows without deleting discovery memory.
- Rebuild FTS: rebuilds the index from `content_items`.
- Reset database data: removes content, analysis, bookmarks, saved searches, and cache, and resets source health; source definitions and safe settings remain.

The CLI `npm run reset-db` is a stronger local developer operation: it recreates the configured SQLite file and schema.
