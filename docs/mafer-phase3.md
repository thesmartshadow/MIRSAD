# MAFER Phase 3: Calibration And Shadow Learning

## Production Contract

The verified Phase 2 deterministic planner remains production. Final ranking remains bounded to 20
semantic candidates with 25% lexical relevance, 75% local multilingual MiniLM similarity, and a 1%
secondary-quality budget. Phase 3 does not modify those modules or parameters.

The following Phase 3 strategies are shadow-only:

- calibrated uncertainty and search-saturation stopping;
- retrieval-utility-adjusted source ordering;
- query-class-aware lexical/semantic fusion;
- multilingual MPNet Arabic expert evaluation;
- near-tie story/platform diversity.

Shadow strategies receive the same stored evidence and persist comparisons, but they do not issue
additional connector calls, change candidate admission, or alter visible results.

## Local Outcomes And Privacy

MIRSAD stores `SEARCH_EXECUTED`, `RESULT_OPENED`, `RESULT_BOOKMARKED`, explicit relevance judgments,
reformulation, zero-result, and source-failure events locally. A click is an interaction signal, not a
relevance judgment. The feedback endpoint derives result rank, source, acquisition mode, query class,
and algorithm versions on the server and verifies that the content belongs to the specified search
session. Context size is bounded. No feedback or search data is sent to external analytics or ML.

Source utility is scoped to query class and source. It uses time-decayed admitted/unique/top-k yield,
duplication, latency, failures, and bounded explicit judgments after minimum evidence. Adjustments are
clamped to +/-8 routing points and remain shadow-only. Web-engine observations retain availability,
canonical yield, latency, CAPTCHA, rate-limit, and timeout separately from long-term discovery utility.

## Versioning And Rollback

Every production session records planner, intent, lattice, router, engine-router, uncertainty, stop,
ranking, semantic-model, and clustering versions. Phase 3 records shadow versions separately. SQLite
configuration snapshots use `verified_production`, `experimental`, `promotion_candidate`, and
`previous_production` slots with benchmark hashes, metrics, timestamp, and reason. A confirmed one-step
rollback restores the previous algorithm configuration without deleting or rewriting content.

## Evidence Graph

The local Evidence Graph contains observed nodes for query, content, canonical URL, source, public
author handle, hashtag, and story. Edges record `discovered_by`, `links_to`, `published_on`, `mentions`,
and algorithmic `same_story` evidence. It is not a Truth Graph and does not infer personal identity,
causality, or factual correctness.

## Evaluation

The Phase 3 development and frozen holdout corpora are separate and SHA-256 guarded. Run:

```bash
npm run evaluate:mafer-phase3
npm run evaluate:mafer-phase3-arabic
npm run evaluate:mafer-phase3-confidence
PYTHONPATH=apps/api .venv/bin/python scripts/evaluate_mafer_phase3_models.py --split development --model minilm
```

The holdout is acceptance evidence, not a tuning input. Model comparisons report language and query
class slices plus initialization, encoding, reranking, memory, and disk cost. Promotion requires
development and independent-holdout gains without material segment regressions, bounded resource cost,
a versioned rollback target, and confidence intervals that support the claimed gain. No experiment is
promoted by documentation alone.
