# MIRSAD Search Quality Evaluation

- Fixture records: 30
- Queries: 20
- Mean Precision@5: 0.2500
- Mean Precision@10: 0.1250
- Returned-set Precision@5: 1.0000
- Returned-set Precision@10: 1.0000
- MRR: 1.0000
- Baseline returned-set Precision@5: 0.8850
- Hard-set Precision@5: 0.2800
- Hard-set returned-set Precision@5: 0.8333
- Hard-set MRR: 0.9222
- Duplicate reduction: 6.67%
- Exact-phrase Precision@5: 0.2857
- Exact-phrase returned-set Precision@5: 1.0000
- Title boost relevance delta: 30.00
- Freshness final-score delta: 18.74
- Engagement final-score delta: 12.12
- Relevant result outranks high-engagement collision: True

Precision@K uses K as its denominator. Returned-set precision is reported separately because the bounded fixture often returns fewer than K candidates. Ranking is deterministic and uses production query/scoring functions with a documented lexical BM25 proxy.
