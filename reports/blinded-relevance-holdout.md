# Blinded Relevance Holdout

## Method

This frozen holdout was added after the current ranking constants were established. The corpus and judgments are separate JSON files, no document contains a ranking hint or relevance label, and the current production query and scoring functions were run unchanged. The set is an engineering holdout, not an assessor-blind academic study.

- Documents: 110
- Queries: 16
- Minimum candidates per query: 12
- Mean candidates per query: 12.25
- Precision@K denominator: K, including when fewer relevant judgments exist
- Unjudged candidates: treated as irrelevant
- Near-duplicate copies: deliberately not double-counted as relevant
- Ranking changes made after baseline: none

## Results

| Segment | Queries | P@5 | P@10 | MRR |
|---|---:|---:|---:|---:|
| Arabic | 5 | 0.0000 | 0.3000 | 0.1286 |
| English | 8 | 0.0000 | 0.2000 | 0.1181 |
| Mixed Arabic/English | 3 | 0.1333 | 0.3333 | 0.4286 |
| Exact phrase | 6 | 0.0000 | 0.2500 | 0.1234 |
| Ambiguous | 2 | 0.0000 | 0.2500 | 0.1340 |
| Hard | 10 | 0.0400 | 0.2600 | 0.2133 |
| Overall | 16 | 0.0250 | 0.2562 | 0.1796 |

## Metric Interpretation

Precision@5 and Precision@10 measure the fraction of all five or ten result slots that are judged relevant. MRR measures only the reciprocal position of the first relevant result. A query with one relevant result at rank 1 therefore has P@5=0.20, P@10=0.10, and MRR=1.00. The previous primary corpus averaged only 1.25 relevant documents per query and often returned fewer than K candidates; its low fixed-K precision and high MRR are mathematically consistent, but unsuitable as standalone evidence of first-page density. This holdout ensures at least ten candidates per query.
The prior hard set averaged 1.40 judged-relevant and 1.87 returned documents per applicable query; 13 of 15 queries placed a relevant result first. Those counts produce P@5=0.2800, P@10=0.1400, and MRR=0.9222 without a formula error.

## Judgment Scope

The ambiguous single-term cases accept multiple legitimate senses and reject only clear brand, promotion, directory, and entertainment collisions. Old but substantive records remain relevant. High-engagement lexical collisions are deliberately present. A tracking-URL near copy is not counted twice, while a distinct report about the same event is judged independently relevant.

## Score Components

| Component | Min | P10 | P25 | Median | Mean | P75 | P90 | Max | Stddev |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| final_score | 31.69 | 43.80 | 57.67 | 74.80 | 66.58 | 75.83 | 77.11 | 82.11 | 12.50 |
| relevance | 77.50 | 100.00 | 100.00 | 100.00 | 98.39 | 100.00 | 100.00 | 100.00 | 5.79 |
| freshness | 0.00 | 0.00 | 8.84 | 95.08 | 64.06 | 98.57 | 98.57 | 98.57 | 42.48 |
| engagement | 0.00 | 3.00 | 8.00 | 77.00 | 55.23 | 93.00 | 98.50 | 100.00 | 40.75 |
| source_confidence | 39.00 | 41.00 | 45.00 | 60.00 | 61.16 | 75.00 | 85.00 | 91.00 | 16.57 |
| cross_source_presence | 0.00 | 0.00 | 0.00 | 0.00 | 12.56 | 30.00 | 45.00 | 60.00 | 19.30 |
| novelty | 12.00 | 20.00 | 28.00 | 36.50 | 45.48 | 75.00 | 82.00 | 92.00 | 24.27 |
| spam_penalty | 0.00 | 0.00 | 0.00 | 0.00 | 0.05 | 0.00 | 0.00 | 5.00 | 0.50 |

## Evidence Boundary

The holdout was created without changing ranking constants and was not used for query-by-query tuning. It is substantially harder and denser than the original suite, but judgments remain locally authored rather than independently supplied by external assessors. The reported values are therefore credible regression evidence, not a claim of general web-search effectiveness.
