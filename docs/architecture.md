# Architecture

## Runtime Topology

MIRSAD runs as two required localhost processes. Vite serves the React application and proxies `/api` during development. FastAPI owns versioned REST routes under `/api/v1`, secrets, connectors, discovery validation, analysis, export generation, and persistence. SQLite is the only required data service. Optional MAFER web discovery adds a locally operated SearXNG service that is contacted only by FastAPI. The optional Docker Compose flow uses the same API/web split and a persistent data volume; it does not replace local execution.

## Backend Boundaries

`mirsad_api/connectors` defines `BaseConnector` and the source implementations. Connectors provide metadata, configuration validation, search, normalization, bounded timeouts/retries, safe error categories, result/malformed counts, HTTP status, and latency. Fixed hosts are enforced by the HTTP helper. RSS URLs are supplied only by server configuration.

The first-class Social Media Collection Layer extends this boundary rather than creating a parallel aggregator. Connector metadata declares source taxonomy, coverage, support level, credential/approval requirements, content types, search modes, sort modes, filters, and boolean/conditional capabilities. The API publishes this non-secret metadata; the React source selector derives presets and controls from it. Social, News, and Developer/Community connectors still enter the same concurrent normalization, deduplication, FTS, ranking, clustering, analytics, history, bookmark, and export flow.

`mirsad_api/discovery` is the MAFER acquisition boundary. Its SearXNG client performs bounded backend-only JSON searches; strict platform URL classifiers independently validate X, Threads, and Reddit candidates; the repository stores canonical discovery memory/support and an expiring cache; optional official oEmbed enrichers retain only safe attribution metadata and discard provider HTML; and the optional Common Crawl adapter looks up capture metadata only for an already validated exact public URL. Discovery never fetches a candidate URL directly.

`mirsad_api/mafer` is the adaptive planning boundary. It owns the deterministic query-intent
fingerprint, immutable bounded query lattice, temporal intent, capability-first resource utility,
Fast/Balanced/Deep budgets, local-memory round zero, discovery-level weighted reciprocal-rank fusion,
evidence completeness, conservative alias evidence, gated expansion, uncertainty, marginal evidence
gain, and stop decisions. It selects retrieval work and never calculates the authoritative final
content score.

Phase 3 adds an observation and shadow-evaluation boundary inside `mirsad_api/mafer`.
`learning.py` records bounded local retrieval-utility evidence without treating clicks as relevance;
`shadow.py`, `calibration.py`, and `shadow_ranking.py` evaluate alternative routing, uncertainty,
stopping, fusion, and near-tie ordering without entering the production control path;
`configuration.py` versions verified/experimental/promotion/previous configurations and supports a
one-step configuration rollback; and `evidence_graph.py` stores observed provenance relationships.
The graph never asserts truth, identity from embeddings, or causality. `routers/quality.py` is the
bounded API surface for explicit feedback, observed summaries, configuration initialization, and
confirmed rollback.

Source and acquisition are orthogonal. `source=x, acquisition_mode=WEB_INDEX` is an indexed public URL, not an X API record. Current acquisition values are `DIRECT_API`, `PUBLIC_API`, `PUBLIC_TIMELINE`, `WEB_INDEX`, `HISTORICAL_INDEX`, `OFFICIAL_EMBED`, and `MANUAL_IMPORT`. Diagnostics, API records, persistence, and exports retain this distinction.

The optional browser-capture companion is an explicit operator action. It submits only a classified
public X/Threads/Reddit content URL and selected visible text to localhost. The data router validates
and canonicalizes the URL without fetching the external page, stores null engagement metrics, and
labels the record `MANUAL_IMPORT`; it has no cookie, login, background-crawl, or CAPTCHA path.

`mirsad_api/domains` contains deterministic analysis:

- `query`: Unicode NFKC, whitespace/case handling, Arabic normalization, language detection, tokens, restrained variants, and bound FTS expressions.
- `engagement`: source-specific logarithmic metric adapters plus a separate deterministic Social Reach metric.
- `ranking`: bounded exact/token/title/BM25 features, relevance-first score composition, exponential freshness, and transparent spam penalties.
- `semantic`: optional local multilingual ONNX reranking, content-hash/model-version caching, capability diagnostics, and lexical fallback.
- `retrieval_metrics`: independently tested fixed-denominator Precision@K, recall, MRR, nDCG, and success metrics.
- `deduplication`: canonical URL, normalized-content SHA-256 fingerprint, and token-Jaccard stages.
- `clustering`: deterministic story groups built from query-dampened corpus-rare identity terms, entity/title evidence, temporal context, and bounded optional local semantic comparisons.
- `analytics`: mention buckets, descriptive trend comparison, distributions, and Arabic/English stopword-aware related terms.

`services/search.py` is the orchestration boundary. It creates a session, executes independent connectors as bounded concurrent tasks, retains successful records during partial failure, stores connector-run diagnostics, writes/indexes content, calculates BM25, deduplicates, ranks, clusters, stores analytics, and finalizes audit events.

`services/read_models.py` builds typed API projections with batched content, duplicate, and cluster lookups. `services/exporting.py` creates versioned JSON and UTF-8 BOM CSV without writing user-selected filesystem paths. `services/data_management.py` contains confirmed local data actions. Routers remain separated by search, analytics, compare, records, data, sources, settings, and system concerns.

## Search Flow

1. Pydantic rejects blank, oversized, or invalid requests.
2. Query processing retains original and normalized forms. MAFER derives an explainable multi-label intent fingerprint and a bounded lattice whose immutable original variant is never discarded; distinctive identifiers are preserved literally.
3. Round zero searches local FTS content, discovery memory, and high-confidence local aliases. Explicit user source choices run concurrently as selected. Automatic selection computes capability and intent fit separately from current availability, then schedules bounded concurrent rounds under the selected Fast/Balanced/Deep budget.
4. After each external round, MAFER records new canonical URLs/candidates/platforms, elapsed time, uncertainty, request use, and an explicit stop reason. Discovery engines and query variants use bounded weighted reciprocal-rank fusion only before content admission. CAPTCHA-blocked and rate-limited engines enter temporary cooldown instead of being retried or permanently considered useless.
5. Connector records are normalized, missing/unknown content languages are resolved conservatively, and known publication times are checked against the requested window in the common pipeline. Each matched source independently contributes up to the configured bounded pre-candidate limit. The union is canonicalized and persisted once per `(source_id, external_id)` without overwriting retrieved text. The display limit is not applied at connector completion or insertion time.
6. FTS triggers synchronize original and normalized title/text/author fields, so Arabic-normalized forms can contribute BM25 evidence without replacing source text.
7. Duplicate groups preserve every original and calculate cross-source distribution metadata. Near-duplicate admission is complete-link within a group to avoid transitive false merges.
8. SQLite FTS5 BM25 plus field-aware phrase, title, coverage, proximity, hashtag, handle, and URL evidence orders candidates. If installed, the local multilingual model still evaluates at most 20 candidates using deterministic round-robin opportunity across each source's lexically ordered queue; this prevents title-bearing or high-volume sources from monopolizing the expensive evaluation stage and does not reserve final positions. Literal hashtag/handle/URL intents bypass semantic ranking. Missing or failed semantic capability falls back to lexical ranking. The frozen 25% lexical / 75% semantic fusion and 1% secondary-quality budget are unchanged.
9. Score components and explanations are persisted per session/item. Best Match places duplicate representatives before their copies so one syndicated story does not consume the first page; originals remain inspectable.
10. Clustering collapses duplicate groups to one evidence representative, blocks plausible pairs by corpus-rare story identifiers, and applies complete-linkage admission so weak transitive bridges cannot join stories. The existing local multilingual model compares only bounded candidate pairs and falls back to lexical evidence when unavailable. Clusters then calculate platform presence, independent-platform diversity, and `First Seen by MIRSAD`; analytics are computed only from collected session records. Fixed windows retain their complete requested span and all-time timelines adapt to the oldest stored publication.
11. The global sort and request cap are applied only after relevance evaluation. Diagnostics retain the full MAFER trace, connector completion order, matched/admitted/final counts per source, per-source relevance distributions, acquisition/cache state, per-engine discovery telemetry, query type, ranking strategy/model state, duplicate reduction, phase timings, and score distributions.
12. Phase 3 records the production outcome and computes versioned shadow alternatives from the same
    evidence. Shadow outputs are persisted for operator comparison but cannot alter connector calls,
    candidate admission, final ordering, or visible results.

## Frontend Boundaries

The frontend uses shadcn/ui exclusively. `lib/api.ts` is the network boundary, `types/api.ts` mirrors API contracts, `lib/i18n.tsx` owns all English/Arabic strings and root `lang`/`dir`, `lib/theme.tsx` owns light/dark/system mode, and `lib/search-state.tsx` makes one persisted session available across analytical routes.

Routes include Search/Results, Analytics, Clusters, Compare, History, Saved Searches, Bookmarks, Sources, System, Settings, and print report. External content is normalized only for safe display, rendered as text with `dir="auto"`, and never passed to raw HTML APIs. The sole `dangerouslySetInnerHTML` usage is the generated shadcn Chart theme stylesheet sourced from static application chart configuration, not retrieved content.

## Reliability And Security

- FastAPI and Vite bind localhost by default; CORS permits configured local origins only.
- Request bodies are capped at 64 KiB; queries are capped at 300 characters and results at 200.
- Connector hosts are fixed, requests have timeouts, retries are at most two, and Retry-After delays are bounded.
- SearXNG and Common Crawl destinations are backend configuration only. Platform classifiers allow only HTTP(S), reject credentials/IP hosts/confusable domains, and require known post/comment URL patterns before persistence or enrichment. Candidate pages are never fetched by the generic discovery layer.
- Error categories distinguish timeout, DNS/network, 401, 403, 404, 429, quota exhaustion, access limitation, restricted capability, upstream 5xx, invalid payload, missing configuration, disabled, and internal connector failure.
- Generic 500 responses prevent trace leakage. Structured user-visible errors never include response bodies, tokens, or stack traces.
- SQLAlchemy and bound SQL parameters protect query values. Settings can mutate only allowlisted database keys and never arbitrary files.
- API responses include anti-sniffing, frame denial, no-referrer, and restrictive browser capability headers.
- JSON export is returned directly; CSV includes a UTF-8 BOM and prefixes formula-like cells to prevent spreadsheet interpretation.

## Audit And Measurement

Audit events record search start/completion, connector failures/recovery, settings changes, data actions, and index rebuilds. Search diagnostics are administrative detail separated from normal results. Deterministic evaluation and performance tools write versioned artifacts under `reports`; live-source verification is supplemental and never required for CI.
