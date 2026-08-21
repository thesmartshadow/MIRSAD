# Relevance Recovery Baseline

Frozen 2026-08-09 before any relevance-recovery ranking change.

## Holdout Integrity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `apps/api/tests/fixtures/blinded_holdout_documents.json` | 34,315 | `321f8f149552cdc8e8e0f6e07dca92972c86650d3ad4dc91e611aca5ba5123ee` |
| `apps/api/tests/fixtures/blinded_holdout_judgments.json` | 2,945 | `c003fca383cf3bd9fb7e0f8bf5ec0eedf748d69fd144b1b803ce5447e2e9db29` |

These files are the frozen final evaluation set. They must not be edited during relevance recovery.
Any objective judgment defect must be reported separately rather than repaired in place.

## Query Set

| ID | Query | Exact | Language | Judged relevant IDs |
| --- | --- | --- | --- | --- |
| q01 | `public health agency` | no | English | ph01, ph02, ph03 |
| q02 | `public health agency` | yes | English | ph01, ph02, ph03 |
| q03 | `mercury` | no | English | me01, me02, me03, me04 |
| q04 | `open data` | no | English | od01, od02, od03 |
| q05 | `open data` | yes | English | od01, od02, od03 |
| q06 | `quasar telemetry` | no | English | qt01, qt02, qt03 |
| q07 | `وزارة التخطيط` | no | Arabic | mp01, mp02, mp03 |
| q08 | `وِزَارَةُ التَّخْطِيط` | yes | Arabic | mp01, mp02, mp03 |
| q09 | `بغداد` | no | Arabic | bg01, bg02, bg03, bg04 |
| q10 | `الذكاء الاصطناعي` | no | Arabic | ai01, ai02, ai03 |
| q11 | `الذَّكَاءُ الاصْطِنَاعِي` | yes | Arabic | ai01, ai02, ai03 |
| q12 | `MIRSAD العراق` | no | Mixed | mx01, mx02, mx03 |
| q13 | `MIRSAD العراق` | yes | Mixed | mx01, mx02, mx03 |
| q14 | `العراق technology` | no | Mixed | mx01, mx02, mx03, mx04, mx05 |
| q15 | `climate adaptation` | no | English | ca01, ca02, ca03, ca13 |
| q16 | `climate adaptation` | yes | English | ca01, ca02, ca03, ca13 |

## Ranking Configuration

| Signal | Weight |
| --- | ---: |
| Relevance | 0.35 |
| Freshness | 0.20 |
| Engagement | 0.15 |
| Source Confidence | 0.10 |
| Cross-Source Presence | 0.10 |
| Novelty | 0.10 |

- Freshness half-life: 48 hours.
- Candidate rule: exact phrase requires the complete normalized token sequence; non-phrase queries
  require one token for one-token queries, both tokens for two-token queries, or 60% for longer
  queries.
- Relevance at freeze: coverage 35, title coverage 15, exact phrase 15, title phrase 15,
  proximity 10, normalized BM25 10, intent-exact 10, capped at 100.
- Secondary signals are multiplied by `(relevance / 100)^2` before the spam penalty.
- Holdout evaluator boundary: its baseline passes token coverage as `bm25_normalized`; it does not
  execute the SQLite FTS5 query. Production search does execute FTS5/BM25 after persistence.

## Frozen Baseline Metrics

| Segment | Queries | P@5 | P@10 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Arabic | 5 | 0.0000 | 0.3000 | 0.1286 |
| English | 8 | 0.0000 | 0.2000 | 0.1181 |
| Mixed Arabic/English | 3 | 0.1333 | 0.3333 | 0.4286 |
| Exact phrase | 6 | 0.0000 | 0.2500 | 0.1234 |
| Ambiguous | 2 | 0.0000 | 0.2500 | 0.1340 |
| Hard | 10 | 0.0400 | 0.2600 | 0.2133 |
| Overall | 16 | 0.0250 | 0.2562 | 0.1796 |

- Documents: 110.
- Minimum candidates per query: 12.
- Mean candidates per query: 12.25.
- Precision denominator is fixed K; unjudged candidates are irrelevant.
- Ranking constants were unchanged when this baseline was produced.

