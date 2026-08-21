# MAFER Phase 2 Baseline

Date: 2026-08-10  
Application: MIRSAD `1.0.0-rc1`

## Scope

This note freezes the production state before MAFER Phase 2 adaptive federated search
intelligence. The Phase 1 reports were reviewed before any Phase 2 production edit.

## Existing Planning Path

1. `process_query()` produces one normalized query, a small Arabic article variant, a coarse
   query type, and conservative FTS tokens.
2. `SearchRequest.sources` is selected by the frontend; the backend calls every requested
   connector concurrently in one round.
3. Web discovery may use at most the configured Phase 1 variants through SearXNG, but there is no
   general query lattice, search budget, resource utility calculation, uncertainty decision, or
   stop reason.
4. The common pipeline filters connector items against the original processed query, gives each
   source bounded pre-candidate admission, unions candidates, persists them, and applies the
   frozen lexical/MiniLM ranking path.
5. Phase 1 discovery memory and cache exist, but search does not query them as a formal round zero.
6. Engine failures are diagnosed per request, but SearXNG engine cooldown and historical discovery
   performance are not modeled separately.

## Concrete Baseline Gaps

- No structured multi-label intent fingerprint or temporal intent.
- No identifier-specific preservation for CVE, GHSA, CWE, commits, packages, repositories,
  domains, URLs, or handles.
- No bounded variant graph with parent/transformation/confidence/drift provenance.
- No source routing derived from capabilities, current availability, and long-term utility.
- No Fast/Balanced/Deep work budgets.
- No round-based local-memory/external retrieval or explainable stop decision.
- No discovery-level weighted reciprocal-rank fusion across variants/engines.
- No explicit evidence-completeness descriptor.
- No gated evidence expansion, drift rejection, or persistent conservative alias graph.
- No uncertainty or marginal-evidence-gain decision loop.

## Immutable Production Baseline

- `ranking.py`: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py`: `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24`
- `clustering.py`: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`
- Production relevance: 25% lexical, 75% semantic, 1% secondary-quality budget.
- Semantic candidate stage: bounded top 20 with Phase 1 source-opportunity selection.

These files, weights, model, thresholds, and frozen relevance holdouts are outside Phase 2 scope.

## Baseline Validation

The immediately preceding Phase 1 final run recorded:

- Backend: 158 passed.
- Frontend: 17 passed.
- Playwright: 11 passed, 2 opt-in live tests skipped.
- Mixed-source cap audit: 11/11 connector-order invariant.
- Lint, TypeScript, production build, SQLite integrity, FTS lifecycle, doctor, and startup smoke:
  passed.

Phase 2 will use a separate search-planning benchmark and will not tune against frozen relevance
holdouts.
