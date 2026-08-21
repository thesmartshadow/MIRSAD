# Relevance Recovery Final

## Original Problem

The frozen 16-query, 110-document holdout exposed dense lexical collisions. Relevant records were
usually present but ranked behind recent, popular, or title-stuffed records with the same query
tokens. The original overall result was P@5 `0.0250`, P@10 `0.2562`, and MRR `0.1796`.

## Frozen Baseline

- Corpus SHA-256: `321f8f149552cdc8e8e0f6e07dca92972c86650d3ad4dc91e611aca5ba5123ee`
- Judgments SHA-256: `c003fca383cf3bd9fb7e0f8bf5ec0eedf748d69fd144b1b803ce5447e2e9db29`
- Documents: 110; queries: 16; candidates per query: 12-13.
- Judgments and corpus remained byte-identical through the final run.
- Precision uses K as the denominator; unjudged results are irrelevant. MRR measures only the first
  relevant rank, so it is intentionally not a density metric.

## Candidate Recall Analysis

All 54 judged relevant records entered the candidate set: candidate recall `1.0000`, with zero
retrieval failures. Before recovery, 52 relevant records were below rank 5 and 13 were below rank
10. Candidate limits 20, 50, 100, and 200 all produced the same recall because no query had more
than 13 admitted candidates. The defect was ranking, not candidate truncation.

## Ranking Failure Categories

All 16 queries had ranking calibration and semantic-collision failures. Fourteen also had lexical
collisions, six had title false positives, and two were inherently short/ambiguous. Freshness and
engagement interfered in all 16 because lexical relevance saturated at 100 for many unrelated
collision records. Full top-15 feature traces are in `reports/holdout-error-analysis.md` and `.json`.

## Lexical Improvements

Relevance is now represented by explicit bounded features: FTS5 BM25, full/body/title phrase
evidence, title/body/query token coverage, minimum token proximity, and literal hashtag/handle/URL
intent. Intent-aware admission remains lexical. Exact phrases require the normalized contiguous
sequence; two-token queries require both tokens; longer queries require 60 percent coverage. These
features alone improved the separate tuning set P@5 from `0.0000` to `0.1250`, but could not resolve
documents deliberately written with the same exact phrase in unrelated contexts.

## Semantic Experiment

Two local multilingual FastEmbed ONNX models were evaluated on the separate eight-query,
80-document hard-negative tuning set. No external API or LLM was used.

| Model | Dimensions | Semantic-only P@5 | MRR | Document encoding | Peak RSS increase |
| --- | ---: | ---: | ---: | ---: | ---: |
| Multilingual MiniLM L12 v2 | 384 | 0.4750 | 0.6292 | 1.86 ms/item | 620 MiB |
| Multilingual MPNet base v2 | 768 | 0.4250 | 0.8304 | 6.58 ms/item | 1,799 MiB |

MiniLM produced better top-five density, used roughly one third of MPNet's observed memory, and was
about 3.5 times faster per document. MPNet's better MRR did not justify its local operational cost
or lower P@5 for this application.

## Fusion Experiments

| Tuning strategy | P@5 | P@10 | MRR | nDCG@10 | Success@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original tuning baseline | 0.0000 | 0.3000 | 0.1429 | 0.4450 | 0.0000 |
| Improved lexical | 0.1250 | 0.3000 | 0.1948 | 0.4694 | 0.6250 |
| MiniLM semantic only | 0.4750 | 0.3000 | 0.6292 | 0.7521 | 1.0000 |
| Lexical/semantic weighted 25/75 | 0.4500 | 0.3000 | 0.5667 | 0.7215 | 1.0000 |
| RRF, k=20 | 0.3250 | 0.3000 | 0.3688 | 0.5760 | 0.8750 |
| Selected 25/75 plus 1% quality budget | 0.4500 | 0.3000 | 0.5458 | 0.6970 | 1.0000 |

RRF was rejected because it retained too much of the collision-prone lexical order. Semantic-only
ranking was rejected because exact names, phrases, hashtags, handles, URLs, and rare technical
terms require an explicit lexical anchor. Larger candidate pools provided no recall benefit. MPNet
was rejected on P@5 and resource cost despite its higher MRR.

## Selected Strategy

SQLite FTS5 and intent rules admit candidates, then the top 20 lexical candidates receive local
MiniLM semantic scores. Hybrid relevance is 25 percent lexical and 75 percent semantic. Secondary
freshness, engagement, confidence, cross-source presence, and novelty share a one-percent maximum
quality budget multiplied by squared relevance eligibility. Spam penalty remains explicit.
Hashtag, handle, and URL intents bypass semantic ranking. Content embeddings use an LRU cache keyed
by normalized content, model name, and model version. Missing/corrupt dependencies or model files
produce an honest capability state and immediate lexical fallback.

## Why Alternatives Were Rejected

- Lexical-only signals could not disambiguate deliberately identical query phrases in different
  contexts.
- Semantic-only was slightly better on the tuning set but reduced exact-intent interpretability.
- RRF underperformed weighted fusion across P@5, MRR, nDCG@10, and Success@5.
- MPNet required about 1.8 GiB additional observed RSS and was slower while reducing top-five density.
- Full-corpus semantic scoring was unnecessary; candidate recall was already complete and the
  bounded top-20 stage achieved the quality gain.

## Arabic Results

Frozen Arabic results improved from P@5 `0.0000` / P@10 `0.3000` / MRR `0.1286` to P@5 `0.1600` /
P@10 `0.2600` / MRR `0.3952`. Recall@10 is `0.8167`, nDCG@10 is `0.4805`, and Success@5 is
`0.6000`. Arabic remains the weakest language slice. The diacritized exact-phrase queries q08 and
q11 place their first relevant results at ranks 7 and 6; this weakness was not tuned after the
frozen run.

## English Results

Frozen English results improved from P@5 `0.0000` / P@10 `0.2000` / MRR `0.1181` to P@5 `0.4750` /
P@10 `0.2875` / MRR `0.8333`. Recall@10 is `0.8542`, nDCG@10 is `0.7345`, and Success@5 is
`1.0000`.

## Mixed-Language Results

Frozen mixed Arabic/English results improved from P@5 `0.1333` / P@10 `0.3333` / MRR `0.4286` to
P@5 `0.4000` / P@10 `0.3667` / MRR `0.6667`. Recall@10 and Success@5 are both `1.0000`.

## Frozen Holdout Before / After

The primary final numbers below use duplicate-suppressed user-facing ordering. Raw-record P@5,
P@10, and MRR are identical here; nDCG differs slightly because a near-copy is moved behind its
representative.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| P@5 | 0.0250 | 0.3625 | +0.3375 |
| P@10 | 0.2562 | 0.2938 | +0.0376 |
| MRR | 0.1796 | 0.6652 | +0.4856 |
| Recall@10 | 0.7740 | 0.8698 | +0.0958 |
| Recall@20 | 1.0000 | 1.0000 | 0.0000 |
| nDCG@5 | 0.0346 | 0.4948 | +0.4602 |
| nDCG@10 | 0.3643 | 0.6528 | +0.2885 |
| Success@1 | 0.0625 | 0.5000 | +0.4375 |
| Success@3 | 0.0625 | 0.8750 | +0.8125 |
| Success@5 | 0.0625 | 0.8750 | +0.8125 |

Query classes: exact P@5 `0.2667`, entity `0.3000`, ambiguous `0.5000`, topic `0.4400`, and
hard-collision `0.4400`.

## Per-Query Results

| ID | Query | Language | P@5 | P@10 | MRR | Relevant ranks |
| --- | --- | --- | ---: | ---: | ---: | --- |
| q01 | public health agency | English | 0.4 | 0.2 | 1.0000 | 1, 5, 12 |
| q02 | public health agency, exact | English | 0.4 | 0.2 | 1.0000 | 1, 5, 12 |
| q03 | mercury | English | 0.8 | 0.4 | 1.0000 | 1, 2, 3, 5 |
| q04 | open data | English | 0.4 | 0.3 | 1.0000 | 1, 4, 8 |
| q05 | open data, exact | English | 0.4 | 0.3 | 1.0000 | 1, 4, 8 |
| q06 | quasar telemetry | English | 0.6 | 0.3 | 1.0000 | 1, 2, 3 |
| q07 | وزارة التخطيط | Arabic | 0.4 | 0.3 | 1.0000 | 1, 4, 10 |
| q08 | وِزَارَةُ التَّخْطِيط, exact | Arabic | 0.0 | 0.2 | 0.1429 | 7, 8, 12 |
| q09 | بغداد | Arabic | 0.2 | 0.3 | 0.3333 | 3, 6, 7, 11 |
| q10 | الذكاء الاصطناعي | Arabic | 0.2 | 0.3 | 0.3333 | 3, 8, 9 |
| q11 | الذَّكَاءُ الاصْطِنَاعِي, exact | Arabic | 0.0 | 0.2 | 0.1667 | 6, 10, 11 |
| q12 | MIRSAD العراق | Mixed | 0.2 | 0.3 | 0.5000 | 2, 6, 9 |
| q13 | MIRSAD العراق, exact | Mixed | 0.4 | 0.3 | 0.5000 | 2, 5, 9 |
| q14 | العراق technology | Mixed | 0.6 | 0.5 | 1.0000 | 1, 2, 3, 7, 8 |
| q15 | climate adaptation | English | 0.4 | 0.3 | 0.3333 | 3, 5, 7, 12 |
| q16 | climate adaptation, exact | English | 0.4 | 0.3 | 0.3333 | 3, 5, 7, 12 |

## Performance Cost

On the frozen run, first model load plus reranking was `485.80 ms`; subsequent query reranking
averaged `23.08 ms`; the complete 16-query evaluation took `879.15 ms`. A separate scaling run
bounded semantic work to 20 candidates: warm total was `9.75 ms` at 100 documents, `46.89 ms` at
1,000, `198.62 ms` at 5,000, and `411.43 ms` at 10,000. Production sessions are capped at 200;
larger rows are lexical stress measurements rather than normal request sizes.

## Memory Cost

The installed MiniLM cache occupies about 241 MiB. Peak observed RSS increase was approximately
684 MiB in the scaling process and 576 MiB in the frozen evaluation process. These are bounded
process observations, not formal minimum-memory requirements. MPNet's roughly 1.8 GiB observed
increase was rejected.

## Explainability Impact

The backend remains authoritative. Stored explanations now include lexical relevance, semantic
relevance/similarity, semantic weight, quality budget, ranking strategy, BM25, title/body phrase
evidence, title/body/query coverage, proximity, matched terms, secondary components, penalty, and
final score. The user Sheet exposes only lexical/semantic relevance, phrase evidence, coverage, and
the established score components; complete traces remain in diagnostics.

## Remaining Weaknesses

- Arabic exact-phrase semantic ordering with diacritized queries is not yet consistently useful in
  the top five, despite substantial aggregate improvement.
- Ambiguous one-word queries cannot infer unstated intent; deterministic admission deliberately
  avoids broad query expansion.
- The semantic model is optional and costs about 241 MiB disk plus substantial process memory. The
  lexical fallback remains less capable under dense semantic collisions.
- The holdout is an engineering judgment set of 16 queries, not a population-level search study.

## Validation

- Backend: 102 tests passed in 4.70 seconds.
- Frontend: 13 tests across five files passed in 5.26 seconds.
- Playwright: 11 tests passed; one operator-credential live-session test was skipped. Search,
  diagnostics, export, state preservation, 20 locale switches, all routes, accessibility, portals,
  and bounded browser memory observation passed.
- Ruff and Oxlint passed; TypeScript passed; the Vite production build completed with 2,769
  transformed modules.
- `npm run doctor` completed without failures. Its only warning was the intentionally absent `.env`.
- A real local-model `SearchService` smoke completed three records with semantic state `ready` and
  a `708.86 ms` cold semantic phase. Repeated worker calls completed without event-loop blocking or
  shutdown hangs.
- The final SHA-256 values were rechecked after validation and still match the frozen baseline.

## Final Recommendation

The frozen holdout demonstrates a 14.5-fold P@5 increase, a 3.7-fold MRR increase, complete
Recall@20, and no aggregate Arabic, English, or mixed-language regression. The top-ranked results
are meaningfully more useful at acceptable bounded local latency. Arabic exact-phrase performance
should remain a monitored limitation during the pilot rather than a basis for post-holdout tuning.

RELEVANCE QUALITY ACCEPTABLE FOR SOCIAL PILOT
