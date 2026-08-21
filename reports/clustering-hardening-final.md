# MIRSAD Clustering Hardening Final

## Original Failure

The persisted supplemental session `681cc5c0-695e-4d04-af38-636f6fcbbd0a` searched
`artificial intelligence` and stored 50 records in 39 clusters. Six multi-member groups were
manually confirmed to lack a shared identifiable story:

- `AiTooLBox`, an AI coursework repository, and the Hacker News item “The Artificial
  Intelligence Revolution (2015)” were grouped together.
- An AI/blockchain repository and the John McCarthy logic article were grouped together.
- Two unrelated AI-learning repositories were grouped together.
- Two unrelated applied-AI/learning repositories were grouped together.
- Three separate chatbot/translator repositories were grouped together.
- Two separate repositories owned by the same account were treated as one story.

The dedicated reproduction fixture preserves the first two observed groups and comparable
broad-topic negatives. The old implementation predicted 14 same-story pairs: 10 true pairs,
4 false merges, and 12 missed pairs. Pairwise precision was `0.7143`, recall `0.4545`, and F1
`0.5556`. Evidence is stored in `reports/clustering-evaluation-baseline.json`.

## Root Cause

The old story test used title/body token Jaccard with permissive combined/body thresholds and
did not receive the processed query terms. Short GitHub names and Hacker News titles therefore
derived most of their overlap from the query itself. For example, the reproduced false pairs
had combined similarity near `0.22` and body similarity near `0.286`, crossing the old `0.22`
and `0.12` admission thresholds using essentially only `artificial` and `intelligence`.

The seed-based grouping then allowed weak pair evidence to define a whole cluster. Duplicate
detection was not the cause: these records had different canonical URLs and content and were
correctly retained as non-duplicates.

## Old Clustering Logic

1. Tokenize concatenated title/body text.
2. Calculate unweighted Jaccard overlap, including the search phrase.
3. Admit a record when a low title/body/combined threshold matched a cluster seed.
4. Do not distinguish common session vocabulary from event identity.
5. Do not use the existing local semantic model, temporal coherence, duplicate representatives,
   or complete-linkage checks.

## New Clustering Logic

The new implementation is confined to `domains/clustering.py`, the clustering call in
`services/search.py`, and reusable pair embeddings in `domains/semantic.py`. Ranking remains
upstream and unchanged.

1. Collapse canonical/duplicate groups to their richest representative for story evidence.
2. Calculate session document frequency and bounded IDF-style token weights.
3. Downweight query terms to 5% in similarity and exclude them from story-identity terms.
4. Define story identifiers conservatively as non-query terms occurring in at most
   `max(4, ceil(5% of representative documents))` records.
5. Build bounded candidate pairs, then calculate title, body, combined lexical, semantic, and
   temporal evidence only for those pairs.
6. Require a shared story identifier for same-language lexical or semantic admission.
7. Apply complete-linkage admission: a new representative must match every representative
   already in the target cluster. This prevents transitive weak bridges.
8. Expand duplicate members after story construction so originals remain inspectable without
   multiplying story evidence.

## Why the Query Phrase Caused False Merges

For a broad query, nearly every candidate contains the query tokens. Treating those tokens as
ordinary document features makes unrelated short records look similar, especially when little
other text exists. Query terms now still contribute minimally to aggregate lexical similarity,
but cannot serve as story identifiers or create candidate blocks. The query continues to govern
retrieval and ranking; it no longer acts as evidence that two results describe the same event.

## Candidate Blocking

Candidate blocks use shared corpus-rare identity terms, conservative title-case Latin entities
that are also rare identity terms, and title bigrams anchored by an identity term. Cross-language
pairs can additionally enter through at most 12 nearest publication-time neighbors within three
days. Blocks larger than 32 and more than 24 candidate neighbors per record are rejected/capped.

On the 49-document judged fixture, only 66 plausible pairs were sent to semantic comparison,
versus 1,176 possible global pairs. At 1,000 synthetic records, 300 of 499,500 possible pairs
were compared (`0.0601%`). No unbounded semantic all-pairs path was introduced.

## Semantic Contribution

The existing local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model and
model-versioned document cache are reused; no model or ranking configuration changed. The model
embeds title plus body and contributes only inside the blocked pair set. Same-language semantic
support requires similarity `>= 0.79` plus shared story identity. Long-gap weak-lexical pairs use
`0.88`. Cross-language pairs require semantic support plus temporal coherence. If the model is
unavailable, clustering falls back to conservative lexical evidence without failing search.

Lexical-only hardened clustering produced zero false merges but missed 15 of 22 paraphrase or
cross-language pairs (precision `1.0000`, recall `0.3182`, F1 `0.4828`). Bounded semantic evidence
recovered the judged pairs without weakening precision.

## Entity / Distinctive-Term Contribution

The implementation separates moderately distinctive terms used for explanation from rarer terms
allowed to establish story identity. Entity overlap is reported, but an organization name alone
cannot admit a same-language pair. This keeps “OpenAI opens office” separate from “OpenAI releases
model” while allowing a shared rare product/event identifier to strengthen a rewritten report.
Arabic identity evidence uses normalized Arabic tokens; no English-only NER dependency was added.

Diagnostics retain per-member reasons such as `shared_distinctive_terms`,
`shared_story_identifiers`, `entity_overlap`, `title_phrase_overlap`, `semantic_similarity`,
`temporal_proximity`, `lexical_story_identity`, and `duplicate_component`.

## Temporal Contribution

Temporal proximity is a soft exponential signal with a 14-day half-life. It does not independently
create a same-language story. Cross-language temporal candidate discovery is limited to three days,
while extremely strong lexical identity can still support older follow-up coverage. Missing dates
remain neutral rather than being treated as current.

## Evaluation Dataset

The separate clustering fixture contains 49 records and six query cases. It includes syndicated
copies, rewritten headlines, social/video/news coverage, GitHub/news references, same-company
different events, same-product different releases, broad-topic negatives, Arabic punctuation and
diacritics, and Arabic/English reports of the same event. Judgments are stored independently from
documents:

- `apps/api/tests/fixtures/clustering_quality_documents.json`
  (`431094b8180a73b1091ec194199c157443953a4b786c3318e98e751c5d4cc452`)
- `apps/api/tests/fixtures/clustering_quality_judgments.json`
  (`d9844f64311cfc888994ea2c46dac6a910256db69c1d66d3a930e69ff4f1ba0a`)

The fixture is purpose-built validation, not a population estimate. Its perfect final score must
not be generalized to all live content.

## Pairwise Precision / Recall / F1

| Strategy | TP | False merges | Missed merges | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Old lexical baseline | 10 | 4 | 12 | 0.7143 | 0.4545 | 0.5556 |
| Hardened lexical fallback | 7 | 0 | 15 | 1.0000 | 0.3182 | 0.4828 |
| Hardened bounded semantic | 22 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

## False Merges Before / After

- Dedicated judged fixture: `4` before, `0` after.
- Persisted/live broad-query comparison: `6` manually confirmed heterogeneous groups before,
  `0` after.
- Repeated-template adversarial case: ten different event identifiers remain ten clusters even
  when every plausible pair is supplied an intentionally high `0.95` semantic similarity.

## Arabic Results

The Arabic cases (`العراق`, `الذكاء الاصطناعي`, and `بغداد`) contain 22 documents and eight judged
same-story pairs. Final results were eight true pairs, zero false merges, and zero misses. Tests
cover diacritics, punctuation, rewritten Arabic reports, a different ministry/event, and an
Arabic/English organization/story bridge. Clustering derives its own identity representation and
does not change frozen ranking normalization.

## Mixed-Language Results

The mixed `technology التكنولوجيا` case contains six documents and three judged pairs. All three
were recovered with zero false merges. Cross-language admission relies on bounded temporal
candidates plus multilingual semantic evidence, not translated query tokens or external services.

## Broad-Query Results

| Query | Documents | Clusters | Largest | False merges |
| --- | ---: | ---: | ---: | ---: |
| `artificial intelligence` | 13 | 9 | 4 | 0 |
| `Microsoft` | 8 | 5 | 3 | 0 |
| `العراق` | 8 | 6 | 3 | 0 |
| `الذكاء الاصطناعي` | 8 | 6 | 3 | 0 |
| `بغداد` | 6 | 4 | 2 | 0 |
| `technology التكنولوجيا` | 6 | 4 | 3 | 0 |

The plain `technology` repeated-template regression contains 30 records describing ten separate
identifier-bearing events. It returns ten three-member clusters and no cross-event merge.

The live rerun session `423db778-c677-4792-8d28-bd6f2a98b107` queried real GitHub and Hacker News
endpoints: both returned HTTP 200, fetched/validated/normalized 50 records each, and MIRSAD retained
50 combined records after its configured limit. Total search time was 3,031 ms; clustering used 117
candidate pairs and 365.72 ms (345.99 ms semantic). It produced 47 clusters. The only three
multi-member groups were exact duplicate Hacker News items (`duplicate_component`); no GitHub/HN
broad-topic story merge remained. The older session used additional sources, but only GitHub and
Hacker News contributed records, so the contributing source families are equivalent.

## Performance

The benchmark uses bounded synthetic story blocks and the existing local model. The 100-record
row includes cold model initialization; later rows reuse the model and overlapping cache entries.
Peak RSS is process-level observational evidence, not a formal memory-leak result.

| Records | Candidate pairs | Blocking ms | Semantic ms | Construction ms | Total ms | Largest cluster | Peak RSS MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 30 | 5.093 | 743.008 | 2.243 | 750.345 | 3 | 696.61 |
| 200 | 60 | 11.251 | 102.954 | 5.549 | 119.756 | 3 | 724.09 |
| 500 | 150 | 34.448 | 315.753 | 29.319 | 379.523 | 3 | 730.30 |
| 1,000 | 300 | 81.065 | 529.615 | 106.994 | 717.675 | 3 | 734.18 |

The first model load increased observed process peak RSS by about 661 MiB. Subsequent 1,000-record
processing increased the already-loaded peak by 3.88 MiB. This is the existing ranking model's
runtime footprint, not a second clustering model. Production collection remains capped at 200
results per request.

## Regression Validation

- Backend: `114 passed` with `.venv/bin/python -m pytest -q`.
- Dedicated clustering: `10 passed`, covering query collisions, organization/event separation,
  rewritten stories, duplicate evidence, Arabic/mixed content, judged pairs, shuffled ordering,
  suspicious-cluster diagnostics, bounded 1,000-record blocking, and repeated templates.
- Frozen relevance regression subset: `21 passed`; holdout document and judgment hashes remain
  `321f8f...3ee` and `c003fca...b29`. Ranking remains lexical admission, top-20 semantic reranking,
  25% lexical / 75% semantic relevance, and a 1% secondary quality budget.
- Frontend Vitest: `13 passed`.
- Playwright: `11 passed`, `2 skipped` opt-in live-session cases, no test failures.
- Ruff/oxlint: pass. TypeScript: pass. Vite production build: pass.
- SQLite: `integrity_check=ok`, zero foreign-key violations, and `152` content rows equal `152`
  FTS rows. Insert/update/delete and confirmed rebuild lifecycle tests pass.
- Live API logs show GitHub and Hacker News HTTP 200 responses and no unexpected exception.

## Remaining Limitations

- The judged fixture is intentionally varied but small. The result establishes regression quality,
  not universal cluster precision.
- Named-entity extraction is conservative for Latin title-case tokens; Arabic relies on normalized
  rare identity terms and multilingual semantics rather than a dedicated Arabic NER model.
- Precision is intentionally favored. A story that dominates a session or lacks any stable rare
  identifier may fragment instead of merging.
- Cross-language reports with weak lexical identity depend on semantic and temporal evidence and
  remain the highest-risk false-merge boundary to monitor during the credentialed pilot.
- Cold local-model memory and startup cost are material, although no additional model was added and
  search retains a lexical fallback.

CLUSTER QUALITY ACCEPTABLE FOR LIVE SOCIAL PILOT
