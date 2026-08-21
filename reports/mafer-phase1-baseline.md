# MAFER Phase 1 Baseline

Date: 2026-08-10  
Application: MIRSAD `1.0.0-rc1`

## Scope

This note records the pre-change acquisition and search architecture for MIRSAD Adaptive
Federated Evidence Retrieval (MAFER) Phase 1. No production code or ranking configuration was
changed before this baseline was recorded.

## Existing Pipeline

1. `SearchRequest` validates the query, selected source keys, filters, time range, result limit,
   and source-specific options.
2. `SearchService.execute()` processes the query and runs registered `BaseConnector`
   implementations concurrently with `asyncio.gather`.
3. Each connector owns fixed-host external access, bounded timeouts/retries, payload parsing,
   normalization to `ConnectorItem`, and structured diagnostics.
4. The common search service performs query matching, language/time/content filtering, content
   persistence, SQLite FTS5/BM25 scoring, local MiniLM reranking, explainable scoring,
   deduplication, hardened story clustering, analytics, and session diagnostics.
5. `ContentItem` preserves the original connector title/text, canonical URL, author, source
   metadata, and normalized fields used by FTS5. `ContentMetric` preserves nullable raw public
   metrics and normalized engagement.
6. `read_models.py` is the authoritative API projection. The frontend and CSV/JSON export consume
   these backend projections and do not reconstruct ranking scores.

## Domain Boundaries

- Connector contract and transport controls: `apps/api/mirsad_api/connectors/base.py`
- Registered connectors: `apps/api/mirsad_api/services/registry.py`
- Query normalization and intent: `apps/api/mirsad_api/domains/query.py`
- Candidate filtering, persistence, orchestration: `apps/api/mirsad_api/services/search.py`
- FTS5 lifecycle: `apps/api/mirsad_api/database.py`
- Frozen lexical/explainable scoring: `apps/api/mirsad_api/domains/ranking.py`
- Frozen local semantic reranking: `apps/api/mirsad_api/domains/semantic.py`
- Deduplication and URL canonicalization: `apps/api/mirsad_api/domains/deduplication.py`
- Hardened story clustering: `apps/api/mirsad_api/domains/clustering.py`
- Analytics: `apps/api/mirsad_api/domains/analytics.py`
- Persistence schema: `apps/api/mirsad_api/models.py`
- API/read models/exports: `apps/api/mirsad_api/services/read_models.py` and `exporting.py`
- Capability-driven source UI: `apps/web/src/components/search/search-form.tsx`
- Provenance presentation and diagnostics: `apps/web/src/components/search/result-card.tsx` and
  `search-diagnostics.tsx`

No discovery-specific service, discovery persistence model, acquisition-mode field, SearXNG
integration, Common Crawl adapter, or `infra/searxng` deployment exists at baseline.

## Connector Extension Point

The safe extension point is a shared discovery domain/service used by the existing X, Threads,
and Reddit connector adapters. It can return the same `ConnectorItem` contract without leaking
platform-specific assumptions into ranking. Direct API behavior remains available when legitimate
credentials exist; configured web discovery can supply validated public URL discoveries when it
does not. Acquisition mode and discovery provenance must travel on the unified connector item and
persist into `ContentItem`, diagnostics, read models, and exports.

## Pre-Candidate Cap Finding

The current service concurrently collects connector results, then concatenates eligible results,
sorts them with a lightweight lexical key, and truncates to `request.limit` **before** persistence,
FTS5/BM25, and MiniLM reranking. The key is deterministic and includes source/external ID, so raw
completion order does not directly decide ties. However, the global pre-ranking truncation prevents
the authoritative frozen relevance pipeline from evaluating all bounded per-source candidates and
can systematically exclude a source. Phase 1 must replace this with bounded per-source admission,
a union/canonicalization step, then unchanged global relevance scoring and final result capping.

## Frozen Ranking Baseline

- Candidate strategy: lexical admission followed by semantic reranking of the top 20 candidates.
- Relevance blend: 25% lexical / 75% semantic.
- Secondary quality budget: 1%.
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Model implementation version: `fastembed-mean-pooling-v1`.
- `ranking.py` SHA-256: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py` SHA-256: `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24`
- `clustering.py` SHA-256: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`
- Frozen holdout documents SHA-256:
  `321f8f149552cdc8e8e0f6e07dca92972c86650d3ad4dc91e611aca5ba5123ee`
- Frozen holdout judgments SHA-256:
  `c003fca383cf3bd9fb7e0f8bf5ec0eedf748d69fd144b1b803ce5447e2e9db29`

Phase 1 will not modify these files, weights, thresholds, model, or holdout fixtures.

## Baseline Validation

Fresh command: `npm test`

- Backend: 135 passed.
- Frontend: 6 files, 14 tests passed.
- Failures: 0.

The repository is a source snapshot without Git metadata; version evidence comes from
`package.json`, `pyproject.toml`, and backend settings.
