# Holdout Error Analysis

Generated before relevance-recovery algorithm changes. Frozen hashes were verified.

## Retrieval Versus Ranking

- Judged relevant documents: 54
- Relevant documents entering the candidate set: 54 (100.00%)
- Candidate misses: 0
- Relevant documents below rank 5: 52
- Relevant documents below rank 10: 13
- Queries classified with ranking failures: 16/16

All judged documents enter the current candidate set; this holdout's primary defect is ranking under dense collisions, not retrieval recall.

## Baseline Metrics

| Segment | Queries | P@5 | P@10 | MRR | R@10 | R@20 | nDCG@5 | nDCG@10 | S@1 | S@3 | S@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Arabic | 5 | 0.0000 | 0.3000 | 0.1286 | 0.9500 | 1.0000 | 0.0000 | 0.4132 | 0.0000 | 0.0000 | 0.0000 |
| English | 8 | 0.0000 | 0.2000 | 0.1181 | 0.6042 | 1.0000 | 0.0000 | 0.2647 | 0.0000 | 0.0000 | 0.0000 |
| Mixed | 3 | 0.1333 | 0.3333 | 0.4286 | 0.9333 | 1.0000 | 0.1844 | 0.5482 | 0.3333 | 0.3333 | 0.3333 |
| Overall | 16 | 0.0250 | 0.2562 | 0.1796 | 0.7740 | 1.0000 | 0.0346 | 0.3643 | 0.0625 | 0.0625 | 0.0625 |

## Failure Categories

- `ENGAGEMENT_INTERFERENCE`: 16 queries
- `FRESHNESS_INTERFERENCE`: 16 queries
- `LEXICAL_COLLISION`: 14 queries
- `RANKING_CALIBRATION`: 16 queries
- `SEMANTIC_COLLISION`: 16 queries
- `SHORT_QUERY_AMBIGUITY`: 2 queries
- `TITLE_FALSE_POSITIVE`: 6 queries

## Candidate Limits

| Pool | Candidate recall | Evaluation latency | Peak traced memory |
| ---: | ---: | ---: | ---: |
| 20 | 1.0000 | 0.2949 ms | 2.67 KiB |
| 50 | 1.0000 | 0.2555 ms | 2.43 KiB |
| 100 | 1.0000 | 0.2445 ms | 2.43 KiB |
| 200 | 1.0000 | 0.2479 ms | 2.43 KiB |

Every query has only 12-13 candidates after intent-aware lexical admission, so pools from 20 through 200 have identical recall. Increasing the production pool cannot repair these ordering failures.

## Query Traces

`BM25` is real in-memory SQLite FTS5 evidence. `Baseline BM25` is the legacy evaluator's coverage proxy retained solely to reproduce the frozen score.

### q01: public health agency

- Expected relevant: ph01, ph02, ph03
- Relevant ranks: [8, 9, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ph04 |  | youtube | 96.70 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 55.00 | 12.00 | 60.00 | 0.00 | 82.11 | Public Health Agency movie trailer |
| 2 | ph08 |  | rss | 95.26 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 91.00 | 60.00 | 10.00 | 52.00 | 0.00 | 80.28 | Television review quotes Public Health Agency |
| 3 | ph06 |  | x | 97.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 50.00 | 0.00 | 35.00 | 0.00 | 78.21 | Public health agency cafe discount |
| 4 | ph09 |  | telegram | 99.47 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 84.00 | 45.00 | 0.00 | 50.00 | 0.00 | 76.81 | Public health agency building traffic |
| 5 | ph11 |  | x | 97.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 95.00 | 42.00 | 0.00 | 25.00 | 0.00 | 75.66 | Public health agency prize promotion |
| 6 | ph05 |  | github | 98.08 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 76.00 | 66.00 | 5.00 | 30.00 | 0.00 | 75.38 | Public health agency logo archive |
| 7 | ph07 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 80.00 | 48.00 | 0.00 | 44.00 | 0.00 | 75.35 | Public health agency careers discussion |
| 8 | ph02 | Y | gdelt | 95.26 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 86.55 | 22.00 | 72.00 | 40.00 | 68.00 | 0.00 | 73.61 | Hospitals respond to public health agency guidance |
| 9 | ph03 | Y | rss | 93.86 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 50.00 | 4.00 | 88.00 | 35.00 | 82.00 | 0.00 | 66.10 | Audit reviews the public health agency response |
| 10 | ph10 |  | rss | 97.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 70.71 | 12.00 | 62.00 | 0.00 | 20.00 | 0.00 | 59.14 | Public health agency directory entry |
| 11 | ph01 | Y | rss | 95.26 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 8.00 | 84.00 | 45.00 | 72.00 | 0.00 | 56.30 | Public health agency issues heat guidance |
| 12 | ph13 |  | telegram | 95.26 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 65.00 | 52.00 | 45.00 | 12.00 | 0.00 | 55.65 | Public health agency issues heat guidance |
| 13 | ph12 |  | rss | 95.26 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 78.00 | 0.00 | 38.00 | 0.00 | 46.75 | History textbook mentions public health agency |

### q02: public health agency

- Expected relevant: ph01, ph02, ph03
- Relevant ranks: [8, 9, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, TITLE_FALSE_POSITIVE, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ph04 |  | youtube | 99.24 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 55.00 | 12.00 | 60.00 | 0.00 | 82.11 | Public Health Agency movie trailer |
| 2 | ph08 |  | rss | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 91.00 | 60.00 | 10.00 | 52.00 | 0.00 | 80.28 | Television review quotes Public Health Agency |
| 3 | ph06 |  | x | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 50.00 | 0.00 | 35.00 | 0.00 | 78.21 | Public health agency cafe discount |
| 4 | ph09 |  | telegram | 97.03 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 84.00 | 45.00 | 0.00 | 50.00 | 0.00 | 76.81 | Public health agency building traffic |
| 5 | ph11 |  | x | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 95.00 | 42.00 | 0.00 | 25.00 | 0.00 | 75.66 | Public health agency prize promotion |
| 6 | ph05 |  | github | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 76.00 | 66.00 | 5.00 | 30.00 | 0.00 | 75.38 | Public health agency logo archive |
| 7 | ph07 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 80.00 | 48.00 | 0.00 | 44.00 | 0.00 | 75.35 | Public health agency careers discussion |
| 8 | ph02 | Y | gdelt | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 86.55 | 22.00 | 72.00 | 40.00 | 68.00 | 0.00 | 73.61 | Hospitals respond to public health agency guidance |
| 9 | ph03 | Y | rss | 96.32 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 50.00 | 4.00 | 88.00 | 35.00 | 82.00 | 0.00 | 66.10 | Audit reviews the public health agency response |
| 10 | ph10 |  | rss | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 70.71 | 12.00 | 62.00 | 0.00 | 20.00 | 0.00 | 59.14 | Public health agency directory entry |
| 11 | ph01 | Y | rss | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 8.00 | 84.00 | 45.00 | 72.00 | 0.00 | 56.30 | Public health agency issues heat guidance |
| 12 | ph13 |  | telegram | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 65.00 | 52.00 | 45.00 | 12.00 | 0.00 | 55.65 | Public health agency issues heat guidance |
| 13 | ph12 |  | rss | 97.76 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 78.00 | 0.00 | 38.00 | 0.00 | 46.75 | History textbook mentions public health agency |

### q03: mercury

- Expected relevant: me01, me02, me03, me04
- Relevant ranks: [8, 9, 11, 12]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, SHORT_QUERY_AMBIGUITY, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | me05 |  | x | 96.18 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 43.00 | 0.00 | 30.00 | 0.00 | 77.01 | Mercury shoes flash sale |
| 2 | me11 |  | x | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 92.00 | 40.00 | 0.00 | 31.00 | 0.00 | 75.61 | Mercury horoscope account |
| 3 | me10 |  | rss | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 75.00 | 57.00 | 0.00 | 40.00 | 0.00 | 75.10 | Mercury newspaper subscription |
| 4 | me07 |  | rss | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 70.00 | 62.00 | 0.00 | 43.00 | 0.00 | 74.88 | Mercury theatre opens |
| 5 | me08 |  | github | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 93.03 | 66.00 | 65.00 | 0.00 | 48.00 | 0.00 | 74.81 | mercury theme package |
| 6 | me06 |  | reddit | 95.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 87.00 | 45.00 | 0.00 | 28.00 | 0.00 | 74.78 | Used Mercury car listing |
| 7 | me09 |  | telegram | 97.67 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 81.00 | 44.00 | 0.00 | 35.00 | 0.00 | 74.76 | Mercury cafe menu |
| 8 | me01 | Y | rss | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 64.84 | 18.00 | 86.00 | 38.00 | 82.00 | 0.00 | 71.27 | Mercury mission returns planetary images |
| 9 | me02 | Y | gdelt | 96.92 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 35.36 | 9.00 | 82.00 | 24.00 | 78.00 | 0.00 | 61.82 | Mercury contamination study published |
| 10 | me12 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 70.71 | 14.00 | 58.00 | 0.00 | 20.00 | 0.00 | 59.04 | Mercury hotel directory |
| 11 | me04 | Y | youtube | 97.67 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 3.13 | 32.00 | 75.00 | 18.00 | 70.00 | 0.00 | 56.73 | Mercury science lecture |
| 12 | me03 | Y | rss | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 5.00 | 88.00 | 22.00 | 74.00 | 0.00 | 55.92 | Mercury temperature record reviewed |

### q04: open data

- Expected relevant: od01, od02, od03
- Relevant ranks: [9, 10, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | od04 |  | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 96.00 | 58.00 | 5.00 | 50.00 | 0.00 | 80.41 | Open Data concert tour |
| 2 | od05 |  | youtube | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 50.00 | 0.00 | 46.00 | 0.00 | 79.31 | Open data unboxing channel |
| 3 | od07 |  | github | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 83.00 | 64.00 | 0.00 | 37.00 | 0.00 | 76.98 | open-data wallpaper |
| 4 | od08 |  | reddit | 96.21 | 100.00 | 0 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 88.00 | 47.00 | 0.00 | 39.00 | 0.00 | 76.23 | Open data phrase debate |
| 5 | od11 |  | x | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 24.00 | 0.00 | 76.21 | Open data giveaway |
| 6 | od06 |  | x | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 97.00 | 42.00 | 0.00 | 27.00 | 0.00 | 76.16 | Open data cafe sale |
| 7 | od09 |  | telegram | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 79.00 | 44.00 | 0.00 | 33.00 | 0.00 | 74.26 | Open data travel package |
| 8 | od10 |  | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 91.70 | 72.00 | 60.00 | 0.00 | 36.00 | 0.00 | 73.74 | Open data textbook advertisement |
| 9 | od02 | Y | rss | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 59.46 | 12.00 | 89.00 | 48.00 | 80.00 | 0.00 | 70.39 | Open data procurement records released |
| 10 | od03 | Y | gdelt | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 35.36 | 4.00 | 84.00 | 42.00 | 86.00 | 0.00 | 63.87 | Researchers assess open data quality |
| 11 | od01 | Y | github | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 3.13 | 7.00 | 82.00 | 55.00 | 75.00 | 0.00 | 57.88 | City open data portal source |
| 12 | od12 |  | rss | 94.77 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 70.00 | 0.00 | 18.00 | 0.00 | 43.80 | Archive index for open data phrase |

### q05: open data

- Expected relevant: od01, od02, od03
- Relevant ranks: [9, 10, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, TITLE_FALSE_POSITIVE, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | od04 |  | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 96.00 | 58.00 | 5.00 | 50.00 | 0.00 | 80.41 | Open Data concert tour |
| 2 | od05 |  | youtube | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 50.00 | 0.00 | 46.00 | 0.00 | 79.31 | Open data unboxing channel |
| 3 | od07 |  | github | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 83.00 | 64.00 | 0.00 | 37.00 | 0.00 | 76.98 | open-data wallpaper |
| 4 | od08 |  | reddit | 68.14 | 100.00 | 0 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 88.00 | 47.00 | 0.00 | 39.00 | 0.00 | 76.23 | Open data phrase debate |
| 5 | od11 |  | x | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 24.00 | 0.00 | 76.21 | Open data giveaway |
| 6 | od06 |  | x | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 97.00 | 42.00 | 0.00 | 27.00 | 0.00 | 76.16 | Open data cafe sale |
| 7 | od09 |  | telegram | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 79.00 | 44.00 | 0.00 | 33.00 | 0.00 | 74.26 | Open data travel package |
| 8 | od10 |  | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 91.70 | 72.00 | 60.00 | 0.00 | 36.00 | 0.00 | 73.74 | Open data textbook advertisement |
| 9 | od02 | Y | rss | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 59.46 | 12.00 | 89.00 | 48.00 | 80.00 | 0.00 | 70.39 | Open data procurement records released |
| 10 | od03 | Y | gdelt | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 35.36 | 4.00 | 84.00 | 42.00 | 86.00 | 0.00 | 63.87 | Researchers assess open data quality |
| 11 | od01 | Y | github | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 3.13 | 7.00 | 82.00 | 55.00 | 75.00 | 0.00 | 57.88 | City open data portal source |
| 12 | od12 |  | rss | 94.77 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 70.00 | 0.00 | 18.00 | 0.00 | 43.80 | Archive index for open data phrase |

### q06: quasar telemetry

- Expected relevant: qt01, qt02, qt03
- Relevant ranks: [8, 10, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | qt04 |  | x | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 42.00 | 0.00 | 40.00 | 0.00 | 77.91 | Quasar Telemetry fashion launch |
| 2 | qt05 |  | github | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 85.00 | 64.00 | 0.00 | 38.00 | 0.00 | 77.38 | quasar-telemetry color theme |
| 3 | qt11 |  | youtube | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 90.00 | 50.00 | 0.00 | 31.00 | 0.00 | 76.03 | Quasar Telemetry music video |
| 4 | qt09 |  | x | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 41.00 | 0.00 | 22.00 | 0.00 | 75.71 | Quasar telemetry contest |
| 5 | qt06 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 91.00 | 45.00 | 0.00 | 30.00 | 0.00 | 75.58 | Quasar Telemetry game clan |
| 6 | qt07 |  | telegram | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 94.00 | 40.00 | 0.00 | 25.00 | 0.00 | 75.31 | Quasar Telemetry token offer |
| 7 | qt08 |  | rss | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 76.00 | 59.00 | 0.00 | 35.00 | 0.00 | 74.95 | Quasar Telemetry restaurant review |
| 8 | qt02 | Y | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 2.00 | 91.00 | 40.00 | 90.00 | 0.00 | 62.40 | Observatory publishes quasar telemetry |
| 9 | qt12 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 70.71 | 5.00 | 57.00 | 0.00 | 15.00 | 0.00 | 57.09 | Quasar Telemetry directory |
| 10 | qt01 | Y | github | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 3.00 | 80.00 | 35.00 | 92.00 | 0.00 | 56.15 | Quasar telemetry parser released |
| 11 | qt03 | Y | youtube | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.78 | 9.00 | 76.00 | 28.00 | 84.00 | 0.00 | 55.31 | Quasar telemetry methods lecture |
| 12 | qt10 |  | rss | 69.44 | 100.00 | 0 | 1 | 100 | 0 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 69.00 | 0.00 | 20.00 | 0.00 | 44.05 | Quasar telemetry glossary |

### q07: وزارة التخطيط

- Expected relevant: mp01, mp02, mp03
- Relevant ranks: [8, 9, 10]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | mp06 |  | rss | 96.09 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 92.00 | 58.00 | 0.00 | 40.00 | 0.00 | 78.03 | مسلسل وزارة التخطيط الخيالي |
| 2 | mp04 |  | x | 92.54 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 42.00 | 0.00 | 32.00 | 0.00 | 77.11 | مقهى قرب وزارة التخطيط |
| 3 | mp05 |  | telegram | 96.09 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 88.00 | 44.00 | 0.00 | 38.00 | 0.00 | 76.11 | ازدحام شارع وزارة التخطيط |
| 4 | mp11 |  | youtube | 97.35 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 89.00 | 49.00 | 0.00 | 30.00 | 0.00 | 75.68 | أغنية وزارة التخطيط |
| 5 | mp09 |  | x | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 97.00 | 40.00 | 0.00 | 21.00 | 0.00 | 75.36 | مسابقة وزارة التخطيط |
| 6 | mp08 |  | github | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 77.00 | 63.00 | 0.00 | 29.00 | 0.00 | 74.90 | شعار وزارة التخطيط |
| 7 | mp07 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 70.00 | 47.00 | 0.00 | 35.00 | 0.00 | 72.58 | وظائف وزارة التخطيط |
| 8 | mp02 | Y | gdelt | 98.65 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 50.00 | 10.00 | 83.00 | 44.00 | 78.00 | 0.00 | 67.00 | تحليل خطة وزارة التخطيط |
| 9 | mp01 | Y | rss | 96.09 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 6.00 | 90.00 | 52.00 | 83.00 | 0.00 | 58.40 | وزارة التخطيط تنشر بيانات التعداد |
| 10 | mp03 | Y | youtube | 97.35 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 18.00 | 74.00 | 32.00 | 76.00 | 0.00 | 57.67 | ندوة عن بيانات وزارة التخطيط |
| 11 | mp10 |  | rss | 94.87 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 67.00 | 0.00 | 16.00 | 0.00 | 43.30 | دليل هاتف وزارة التخطيط |
| 12 | mp12 |  | rss | 98.65 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 65.00 | 0.00 | 12.00 | 0.00 | 42.85 | فهرس ذكر وزارة التخطيط |

### q08: وِزَارَةُ التَّخْطِيط

- Expected relevant: mp01, mp02, mp03
- Relevant ranks: [8, 9, 10]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, TITLE_FALSE_POSITIVE, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | mp06 |  | rss | 94.02 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 92.00 | 58.00 | 0.00 | 40.00 | 0.00 | 78.03 | مسلسل وزارة التخطيط الخيالي |
| 2 | mp04 |  | x | 88.72 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 42.00 | 0.00 | 32.00 | 0.00 | 77.11 | مقهى قرب وزارة التخطيط |
| 3 | mp05 |  | telegram | 94.02 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 88.00 | 44.00 | 0.00 | 38.00 | 0.00 | 76.11 | ازدحام شارع وزارة التخطيط |
| 4 | mp11 |  | youtube | 95.93 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 89.00 | 49.00 | 0.00 | 30.00 | 0.00 | 75.68 | أغنية وزارة التخطيط |
| 5 | mp09 |  | x | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 97.00 | 40.00 | 0.00 | 21.00 | 0.00 | 75.36 | مسابقة وزارة التخطيط |
| 6 | mp08 |  | github | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 77.00 | 63.00 | 0.00 | 29.00 | 0.00 | 74.90 | شعار وزارة التخطيط |
| 7 | mp07 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 70.00 | 47.00 | 0.00 | 35.00 | 0.00 | 72.58 | وظائف وزارة التخطيط |
| 8 | mp02 | Y | gdelt | 97.92 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 50.00 | 10.00 | 83.00 | 44.00 | 78.00 | 0.00 | 67.00 | تحليل خطة وزارة التخطيط |
| 9 | mp01 | Y | rss | 94.02 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 6.00 | 90.00 | 52.00 | 83.00 | 0.00 | 58.40 | وزارة التخطيط تنشر بيانات التعداد |
| 10 | mp03 | Y | youtube | 95.93 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 18.00 | 74.00 | 32.00 | 76.00 | 0.00 | 57.67 | ندوة عن بيانات وزارة التخطيط |
| 11 | mp10 |  | rss | 92.18 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 67.00 | 0.00 | 16.00 | 0.00 | 43.30 | دليل هاتف وزارة التخطيط |
| 12 | mp12 |  | rss | 97.92 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 65.00 | 0.00 | 12.00 | 0.00 | 42.85 | فهرس ذكر وزارة التخطيط |

### q09: بغداد

- Expected relevant: bg01, bg02, bg03, bg04
- Relevant ranks: [7, 8, 10, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, SHORT_QUERY_AMBIGUITY, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | bg05 |  | x | 97.63 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 34.00 | 0.00 | 77.21 | عطر بغداد الجديد |
| 2 | bg06 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 94.00 | 45.00 | 0.00 | 37.00 | 0.00 | 77.01 | لعبة بغداد الإلكترونية |
| 3 | bg07 |  | rss | 97.63 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 82.00 | 58.00 | 0.00 | 36.00 | 0.00 | 76.13 | مطعم بغداد يفتتح فرعا |
| 4 | bg08 |  | github | 98.41 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 76.00 | 64.00 | 0.00 | 40.00 | 0.00 | 75.95 | سمة بغداد للألوان |
| 5 | bg11 |  | youtube | 99.20 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 90.00 | 50.00 | 0.00 | 28.00 | 0.00 | 75.73 | أغنية بغداد |
| 6 | bg09 |  | x | 99.20 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 40.00 | 0.00 | 22.00 | 0.00 | 75.61 | مسابقة بغداد |
| 7 | bg04 | Y | telegram | 98.41 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 25.00 | 55.00 | 12.00 | 68.00 | 0.00 | 71.68 | تحديث طقس بغداد |
| 8 | bg01 | Y | gdelt | 97.63 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 59.46 | 14.00 | 82.00 | 55.00 | 80.00 | 0.00 | 70.69 | بغداد تستضيف مؤتمرا إقليميا |
| 9 | bg10 |  | rss | 99.20 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 71.00 | 57.00 | 0.00 | 33.00 | 5.00 | 68.53 | فندق بغداد الدولي |
| 10 | bg02 | Y | rss | 95.38 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 7.00 | 88.00 | 38.00 | 78.00 | 0.00 | 61.45 | مشروع نقل عام جديد في بغداد |
| 11 | bg03 | Y | youtube | 99.20 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 3.13 | 20.00 | 73.00 | 20.00 | 75.00 | 0.00 | 55.43 | محاضرة عن تاريخ بغداد |
| 12 | bg12 |  | rss | 99.20 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 66.00 | 0.00 | 14.00 | 5.00 | 38.00 | دليل كلمة بغداد |

### q10: الذكاء الاصطناعي

- Expected relevant: ai01, ai02, ai03
- Relevant ranks: [8, 9, 10]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ai04 |  | x | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 42.00 | 0.00 | 32.00 | 0.00 | 77.11 | قميص الذكاء الاصطناعي |
| 2 | ai11 |  | youtube | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 92.00 | 49.00 | 0.00 | 29.00 | 0.00 | 76.03 | أغنية الذكاء الاصطناعي |
| 3 | ai06 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 89.00 | 45.00 | 0.00 | 35.00 | 0.00 | 75.78 | فريق لعبة الذكاء الاصطناعي |
| 4 | ai05 |  | telegram | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 96.00 | 40.00 | 0.00 | 25.00 | 0.00 | 75.61 | عملة الذكاء الاصطناعي |
| 5 | ai09 |  | x | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 40.00 | 0.00 | 20.00 | 0.00 | 75.41 | مسابقة الذكاء الاصطناعي |
| 6 | ai07 |  | rss | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 78.00 | 57.00 | 0.00 | 38.00 | 0.00 | 75.35 | مطعم الذكاء الاصطناعي |
| 7 | ai08 |  | github | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 73.00 | 63.00 | 0.00 | 40.00 | 0.00 | 75.13 | سمة الذكاء الاصطناعي |
| 8 | ai03 | Y | youtube | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 18.00 | 75.00 | 32.00 | 80.00 | 0.00 | 61.40 | محاضرة حوكمة الذكاء الاصطناعي |
| 9 | ai01 | Y | rss | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 5.00 | 90.00 | 58.00 | 84.00 | 0.00 | 58.95 | الذكاء الاصطناعي في الخدمات العامة |
| 10 | ai02 | Y | github | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 11.00 | 79.00 | 35.00 | 86.00 | 0.00 | 58.42 | أداة تدقيق نماذج الذكاء الاصطناعي |
| 11 | ai10 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 68.00 | 0.00 | 18.00 | 0.00 | 43.75 | قاموس الذكاء الاصطناعي |
| 12 | ai12 |  | rss | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.78 | 3.00 | 61.00 | 0.00 | 16.00 | 0.00 | 43.31 | فهرس الذكاء الاصطناعي |

### q11: الذَّكَاءُ الاصْطِنَاعِي

- Expected relevant: ai01, ai02, ai03
- Relevant ranks: [8, 9, 10]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, TITLE_FALSE_POSITIVE, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ai04 |  | x | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 42.00 | 0.00 | 32.00 | 0.00 | 77.11 | قميص الذكاء الاصطناعي |
| 2 | ai11 |  | youtube | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 92.00 | 49.00 | 0.00 | 29.00 | 0.00 | 76.03 | أغنية الذكاء الاصطناعي |
| 3 | ai06 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 89.00 | 45.00 | 0.00 | 35.00 | 0.00 | 75.78 | فريق لعبة الذكاء الاصطناعي |
| 4 | ai05 |  | telegram | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 96.00 | 40.00 | 0.00 | 25.00 | 0.00 | 75.61 | عملة الذكاء الاصطناعي |
| 5 | ai09 |  | x | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 40.00 | 0.00 | 20.00 | 0.00 | 75.41 | مسابقة الذكاء الاصطناعي |
| 6 | ai07 |  | rss | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 78.00 | 57.00 | 0.00 | 38.00 | 0.00 | 75.35 | مطعم الذكاء الاصطناعي |
| 7 | ai08 |  | github | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 73.00 | 63.00 | 0.00 | 40.00 | 0.00 | 75.13 | سمة الذكاء الاصطناعي |
| 8 | ai03 | Y | youtube | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 18.00 | 75.00 | 32.00 | 80.00 | 0.00 | 61.40 | محاضرة حوكمة الذكاء الاصطناعي |
| 9 | ai01 | Y | rss | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 5.00 | 90.00 | 58.00 | 84.00 | 0.00 | 58.95 | الذكاء الاصطناعي في الخدمات العامة |
| 10 | ai02 | Y | github | 98.44 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 11.00 | 79.00 | 35.00 | 86.00 | 0.00 | 58.42 | أداة تدقيق نماذج الذكاء الاصطناعي |
| 11 | ai10 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 68.00 | 0.00 | 18.00 | 0.00 | 43.75 | قاموس الذكاء الاصطناعي |
| 12 | ai12 |  | rss | 99.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.78 | 3.00 | 61.00 | 0.00 | 16.00 | 0.00 | 43.31 | فهرس الذكاء الاصطناعي |

### q12: MIRSAD العراق

- Expected relevant: mx01, mx02, mx03
- Relevant ranks: [7, 8, 9]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | mx06 |  | x | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 28.00 | 0.00 | 76.61 | MIRSAD العراق fashion sale |
| 2 | mx09 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 82.00 | 58.00 | 0.00 | 36.00 | 0.00 | 75.85 | MIRSAD العراق restaurant |
| 3 | mx08 |  | reddit | 98.14 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 90.00 | 45.00 | 0.00 | 34.00 | 0.00 | 75.83 | MIRSAD العراق game clan |
| 4 | mx10 |  | github | 97.53 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 77.00 | 64.00 | 0.00 | 39.00 | 0.00 | 75.73 | MIRSAD العراق color theme |
| 5 | mx11 |  | x | 98.75 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 40.00 | 0.00 | 20.00 | 0.00 | 75.41 | MIRSAD العراق giveaway |
| 6 | mx07 |  | telegram | 98.14 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 95.00 | 40.00 | 0.00 | 22.00 | 0.00 | 75.16 | عملة MIRSAD العراق |
| 7 | mx02 | Y | rss | 98.75 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 8.00 | 89.00 | 40.00 | 82.00 | 0.00 | 62.30 | دراسة MIRSAD العراق |
| 8 | mx03 | Y | youtube | 98.14 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 14.00 | 75.00 | 35.00 | 80.00 | 0.00 | 57.87 | MIRSAD العراق technical briefing |
| 9 | mx01 | Y | github | 97.53 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 4.00 | 84.00 | 45.00 | 88.00 | 0.00 | 57.30 | MIRSAD العراق localization release |
| 10 | mx12 |  | rss | 98.75 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 62.00 | 0.00 | 14.00 | 0.00 | 42.60 | MIRSAD العراق directory |
| 11 | mx04 |  | rss | 93.38 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 3.13 | 5.00 | 87.00 | 30.00 | 78.00 | 0.00 | 39.66 | العراق technology policy report |
| 12 | mx05 |  | github | 95.42 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 0.78 | 6.00 | 80.00 | 25.00 | 76.00 | 0.00 | 38.63 | العراق technology terminology dataset |

### q13: MIRSAD العراق

- Expected relevant: mx01, mx02, mx03
- Relevant ranks: [7, 8, 9]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, TITLE_FALSE_POSITIVE, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | mx06 |  | x | 96.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 28.00 | 0.00 | 76.61 | MIRSAD العراق fashion sale |
| 2 | mx09 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 82.00 | 58.00 | 0.00 | 36.00 | 0.00 | 75.85 | MIRSAD العراق restaurant |
| 3 | mx08 |  | reddit | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 90.00 | 45.00 | 0.00 | 34.00 | 0.00 | 75.83 | MIRSAD العراق game clan |
| 4 | mx10 |  | github | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 77.00 | 64.00 | 0.00 | 39.00 | 0.00 | 75.73 | MIRSAD العراق color theme |
| 5 | mx11 |  | x | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 40.00 | 0.00 | 20.00 | 0.00 | 75.41 | MIRSAD العراق giveaway |
| 6 | mx07 |  | telegram | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 95.00 | 40.00 | 0.00 | 22.00 | 0.00 | 75.16 | عملة MIRSAD العراق |
| 7 | mx02 | Y | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 8.00 | 89.00 | 40.00 | 82.00 | 0.00 | 62.30 | دراسة MIRSAD العراق |
| 8 | mx03 | Y | youtube | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 8.84 | 14.00 | 75.00 | 35.00 | 80.00 | 0.00 | 57.87 | MIRSAD العراق technical briefing |
| 9 | mx01 | Y | github | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 4.00 | 84.00 | 45.00 | 88.00 | 0.00 | 57.30 | MIRSAD العراق localization release |
| 10 | mx12 |  | rss | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 0.00 | 62.00 | 0.00 | 14.00 | 0.00 | 42.60 | MIRSAD العراق directory |
| 11 | mx04 |  | rss | 89.37 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 3.13 | 5.00 | 87.00 | 30.00 | 78.00 | 0.00 | 39.66 | العراق technology policy report |
| 12 | mx05 |  | github | 92.09 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 0.78 | 6.00 | 80.00 | 25.00 | 76.00 | 0.00 | 38.63 | العراق technology terminology dataset |

### q14: العراق technology

- Expected relevant: mx01, mx02, mx03, mx04, mx05
- Relevant ranks: [1, 2, 9, 10, 11]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | mx04 | Y | rss | 98.17 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 3.13 | 5.00 | 87.00 | 30.00 | 78.00 | 0.00 | 55.88 | العراق technology policy report |
| 2 | mx05 | Y | github | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.78 | 6.00 | 80.00 | 25.00 | 76.00 | 0.00 | 54.16 | العراق technology terminology dataset |
| 3 | mx06 |  | x | 95.83 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 98.57 | 100.00 | 41.00 | 0.00 | 28.00 | 0.00 | 52.12 | MIRSAD العراق fashion sale |
| 4 | mx09 |  | rss | 99.42 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 95.76 | 82.00 | 58.00 | 0.00 | 36.00 | 0.00 | 51.66 | MIRSAD العراق restaurant |
| 5 | mx08 |  | reddit | 97.23 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 97.15 | 90.00 | 45.00 | 0.00 | 34.00 | 0.00 | 51.65 | MIRSAD العراق game clan |
| 6 | mx10 |  | github | 96.52 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 94.39 | 77.00 | 64.00 | 0.00 | 39.00 | 0.00 | 51.59 | MIRSAD العراق color theme |
| 7 | mx11 |  | x | 97.95 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 98.57 | 98.00 | 40.00 | 0.00 | 20.00 | 0.00 | 51.40 | MIRSAD العراق giveaway |
| 8 | mx07 |  | telegram | 97.23 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 98.57 | 95.00 | 40.00 | 0.00 | 22.00 | 0.00 | 51.25 | عملة MIRSAD العراق |
| 9 | mx02 | Y | rss | 97.95 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 25.00 | 8.00 | 89.00 | 40.00 | 82.00 | 0.00 | 43.52 | دراسة MIRSAD العراق |
| 10 | mx03 | Y | youtube | 97.23 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 8.84 | 14.00 | 75.00 | 35.00 | 80.00 | 0.00 | 40.86 | MIRSAD العراق technical briefing |
| 11 | mx01 | Y | github | 96.52 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 0.00 | 4.00 | 84.00 | 45.00 | 88.00 | 0.00 | 40.52 | MIRSAD العراق localization release |
| 12 | mx12 |  | rss | 97.95 | 100.00 | 1 | 0 | 50 | 100 | 100 | 100 | 100 | 100 | 77.50 | 0.00 | 0.00 | 62.00 | 0.00 | 14.00 | 0.00 | 31.69 | MIRSAD العراق directory |

### q15: climate adaptation

- Expected relevant: ca01, ca02, ca03, ca13
- Relevant ranks: [9, 10, 11, 12]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ca05 |  | youtube | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 99.00 | 50.00 | 0.00 | 32.00 | 0.00 | 77.76 | Climate adaptation dance challenge |
| 2 | ca04 |  | x | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 35.00 | 0.00 | 77.31 | Climate Adaptation clothing launch |
| 3 | ca06 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 93.00 | 45.00 | 0.00 | 40.00 | 0.00 | 76.88 | Climate Adaptation game expansion |
| 4 | ca09 |  | github | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 78.00 | 64.00 | 0.00 | 38.00 | 0.00 | 75.78 | climate-adaptation editor theme |
| 5 | ca08 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 81.00 | 58.00 | 0.00 | 36.00 | 0.00 | 75.70 | Climate adaptation restaurant menu |
| 6 | ca12 |  | youtube | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 88.00 | 49.00 | 0.00 | 30.00 | 0.00 | 75.53 | Climate Adaptation music video |
| 7 | ca07 |  | telegram | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 96.00 | 40.00 | 0.00 | 24.00 | 0.00 | 75.51 | Climate adaptation token promotion |
| 8 | ca10 |  | x | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 39.00 | 0.00 | 20.00 | 0.00 | 75.31 | Climate adaptation giveaway |
| 9 | ca13 | Y | gdelt | 91.36 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 70.71 | 13.00 | 83.00 | 60.00 | 78.00 | 0.00 | 73.19 | Flood projects begin under climate adaptation plan |
| 10 | ca02 | Y | gdelt | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 9.00 | 84.00 | 50.00 | 82.00 | 0.00 | 62.95 | Cities measure climate adaptation outcomes |
| 11 | ca01 | Y | rss | 96.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 5.00 | 91.00 | 60.00 | 88.00 | 0.00 | 59.65 | Climate adaptation plan funds flood barriers |
| 12 | ca03 | Y | github | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.78 | 7.00 | 79.00 | 38.00 | 86.00 | 0.00 | 56.51 | Climate adaptation indicator toolkit |
| 13 | ca11 |  | rss | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 70.00 | 0.00 | 18.00 | 0.00 | 43.95 | Climate adaptation glossary |

### q16: climate adaptation

- Expected relevant: ca01, ca02, ca03, ca13
- Relevant ranks: [9, 10, 11, 12]
- Candidate recall: 1.0000
- Failure classification: RANKING_CALIBRATION, LEXICAL_COLLISION, SEMANTIC_COLLISION, TITLE_FALSE_POSITIVE, FRESHNESS_INTERFERENCE, ENGAGEMENT_INTERFERENCE

| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |
| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | ca05 |  | youtube | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 99.00 | 50.00 | 0.00 | 32.00 | 0.00 | 77.76 | Climate adaptation dance challenge |
| 2 | ca04 |  | x | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 100.00 | 41.00 | 0.00 | 35.00 | 0.00 | 77.31 | Climate Adaptation clothing launch |
| 3 | ca06 |  | reddit | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 93.00 | 45.00 | 0.00 | 40.00 | 0.00 | 76.88 | Climate Adaptation game expansion |
| 4 | ca09 |  | github | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 94.39 | 78.00 | 64.00 | 0.00 | 38.00 | 0.00 | 75.78 | climate-adaptation editor theme |
| 5 | ca08 |  | rss | 100.00 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 95.76 | 81.00 | 58.00 | 0.00 | 36.00 | 0.00 | 75.70 | Climate adaptation restaurant menu |
| 6 | ca12 |  | youtube | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 97.15 | 88.00 | 49.00 | 0.00 | 30.00 | 0.00 | 75.53 | Climate Adaptation music video |
| 7 | ca07 |  | telegram | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 96.00 | 40.00 | 0.00 | 24.00 | 0.00 | 75.51 | Climate adaptation token promotion |
| 8 | ca10 |  | x | 99.22 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 98.57 | 98.00 | 39.00 | 0.00 | 20.00 | 0.00 | 75.31 | Climate adaptation giveaway |
| 9 | ca13 | Y | gdelt | 91.36 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 70.71 | 13.00 | 83.00 | 60.00 | 78.00 | 0.00 | 73.19 | Flood projects begin under climate adaptation plan |
| 10 | ca02 | Y | gdelt | 96.94 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 25.00 | 9.00 | 84.00 | 50.00 | 82.00 | 0.00 | 62.95 | Cities measure climate adaptation outcomes |
| 11 | ca01 | Y | rss | 96.21 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 5.00 | 91.00 | 60.00 | 88.00 | 0.00 | 59.65 | Climate adaptation plan funds flood barriers |
| 12 | ca03 | Y | github | 98.45 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.78 | 7.00 | 79.00 | 38.00 | 86.00 | 0.00 | 56.51 | Climate adaptation indicator toolkit |
| 13 | ca11 |  | rss | 97.69 | 100.00 | 1 | 1 | 100 | 100 | 100 | 100 | 100 | 100 | 100.00 | 0.00 | 1.00 | 70.00 | 0.00 | 18.00 | 0.00 | 43.95 | Climate adaptation glossary |

## Root Cause

Candidate recall is complete. The dominant failures are semantically different records that repeat the exact query phrase in both title and body, making coverage, phrase, proximity, rarity, and often FTS BM25 nearly indistinguishable. Relevance saturates at 100, so freshness and engagement order the collision set. This is a ranking and semantic disambiguation problem; larger candidate pools or simple query-token weights cannot solve it.
