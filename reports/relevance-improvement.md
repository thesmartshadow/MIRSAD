# Relevance Improvement

The same frozen fixtures and judgments were evaluated through the legacy and current pipelines.
Precision@K uses K; returned-set precision divides by candidates returned up to K.

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Primary P@5 | 0.2500 | 0.2500 | +0.0000 |
| Primary P@10 | 0.1250 | 0.1250 | +0.0000 |
| Primary returned-set P@5 | 0.8850 | 1.0000 | +0.1150 |
| Primary returned-set P@10 | 0.8850 | 1.0000 | +0.1150 |
| Primary MRR | 1.0000 | 1.0000 | +0.0000 |
| Hard P@5 | 0.2800 | 0.2800 | +0.0000 |
| Hard P@10 | 0.1400 | 0.1400 | +0.0000 |
| Hard returned-set P@5 | 0.6711 | 0.8333 | +0.1622 |
| Hard returned-set P@10 | 0.6667 | 0.8333 | +0.1666 |
| Hard MRR | 0.8022 | 0.9222 | +0.1200 |

## Interpretation

Candidate generation now requires all tokens for two-token queries and 60% coverage for longer queries. Ranking uses bounded phrase, title, proximity, coverage, intent, and BM25 signals. Supporting signals are relevance-gated, so they cannot rescue a weak lexical match.

The hard set intentionally retains ambiguous lexical collisions that cannot be resolved reliably without semantic context. These candidates remain visible rather than being silently over-filtered. Semantic reranking was not enabled because no measured benefit was established.

## Language And Grouping Checks

| Check | Precision | Recall / MRR |
|---|---:|---:|
| Arabic returned-set P@5 / MRR | 1.0000 | 1.0000 |
| English returned-set P@5 / MRR | 1.0000 | 1.0000 |
| Mixed-language returned-set P@5 / MRR | 1.0000 | 1.0000 |
| Judged duplicate pairs | 1.0000 | 1.0000 |
| Judged cluster pairs | 1.0000 | 1.0000 |

## Score Calibration

| Component | Min | Max | Mean | Median | Stddev | P10 | P25 | P75 | P90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| final_score | 22.27 | 86.71 | 62.26 | 70.61 | 17.78 | 32.26 | 52.47 | 72.53 | 73.92 |
| relevance | 40.00 | 100.00 | 88.89 | 100.00 | 16.80 | 57.50 | 77.50 | 100.00 | 100.00 |
| freshness | 0.78 | 98.57 | 79.79 | 93.03 | 26.66 | 35.36 | 70.71 | 95.76 | 98.57 |
| engagement | 1.00 | 100.00 | 34.79 | 17.50 | 34.92 | 3.00 | 11.00 | 45.00 | 98.00 |
| source_confidence | 70.00 | 70.00 | 70.00 | 70.00 | 0.00 | 70.00 | 70.00 | 70.00 | 70.00 |
| cross_source_presence | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| novelty | 100.00 | 100.00 | 100.00 | 100.00 | 0.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| spam_penalty | 0.00 | 5.00 | 0.36 | 0.00 | 1.29 | 0.00 | 0.00 | 0.00 | 0.00 |

Source Confidence, Cross-Source Presence, and Novelty are constant in the hard ranking fixture. Their zero variance is a fixture limitation, not evidence that these signals are constant in stored searches.

## Residual Errors

- `ENGAGEMENT_OVERWEIGHTED`: query `climate` returned `e17` within the first five candidates.
- `ENGAGEMENT_OVERWEIGHTED`: query `climate` returned `e03` within the first five candidates.
- `ENGAGEMENT_OVERWEIGHTED`: query `open source` returned `h01` within the first five candidates.
- `AMBIGUOUS_QUERY`: query `open source` returned `e06` within the first five candidates.
- `ENGAGEMENT_OVERWEIGHTED`: query `artificial intelligence governance` returned `h03` within the first five candidates.
- `ENGAGEMENT_OVERWEIGHTED`: query `وزارة الصحة` returned `h05` within the first five candidates.
- `ENGAGEMENT_OVERWEIGHTED`: query `وِزَارَةُ الصِّحَّة` returned `h05` within the first five candidates.
