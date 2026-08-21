# Scoring And Search Quality

MIRSAD ranking is deterministic, inspectable, and not a truth score. Popularity, cross-source distribution, or Source Confidence never establishes factual accuracy.

MAFER adaptive planning happens before this scoring layer. Its query lattice, resource utility,
local-memory round, evidence uncertainty, and discovery-level weighted reciprocal-rank fusion decide
which bounded candidates receive normal processing. Discovery RRF does not replace or contribute an
unbounded signal to Final Score. The production 25% lexical / 75% semantic fusion, 20-candidate
semantic bound, and one-percent secondary-quality budget remain authoritative.

Phase 3 query-aware lexical/semantic fusion and near-tie diversity are shadow experiments only. Their
orders are stored for comparison and are never substituted for the authoritative score or visible
result order. The larger multilingual MPNet experiment is also shadow-only; production continues to
use multilingual MiniLM with lexical fallback.

## Lexical Fallback Formula

```text
FinalScore =
  0.35 * Relevance
+ 0.20 * Freshness
+ 0.15 * Engagement
+ 0.10 * SourceConfidence
+ 0.10 * CrossSourcePresence
+ 0.10 * Novelty
- SpamPenalty
```

Positive components and Final Score are clamped to `0..100`. Settings reject an enabled weight total other than `1.0` within floating-point tolerance. This remains the complete ranking path when the optional local semantic model is disabled or unavailable.

## Relevance

The relevance component combines these bounded signals before clamping to `0..100`:

- 35% exact token coverage across title/text
- 15% title token coverage
- 15% exact normalized phrase presence in title/text
- 15% exact phrase presence in the title
- 10% minimum query-token proximity
- 10% normalized SQLite FTS5 BM25 strength
- 10% exact hashtag, handle, or URL-intent match when that intent applies

Candidate retrieval and final ranking are separate. Exact phrases require a contiguous normalized token sequence; two-token keyword queries require both tokens; longer queries require at least 60% token coverage. Tokens match token boundaries rather than arbitrary substrings. The FTS query is bound and restricted to current-session candidate IDs before BM25 contributes to ranking. Original and normalized queries, ordered tokens, intent, variants, variant reasons, and matched terms remain inspectable.

## Two-Stage Reranking

When the optional local model is installed, MIRSAD lexically orders each source's bounded admitted
candidates and selects at most 20 for semantic evaluation by deterministic source round-robin. This
prevents a high-volume or title-bearing source from monopolizing the expensive stage; it does not
reserve final positions or force equal representation. The selected model is
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, executed locally through FastEmbed
ONNX with no external API. Document vectors are cached by normalized content hash, model name, and
model version. Hashtag, handle, and URL queries remain lexical-only because literal identity is more
reliable for those intents.

```text
SemanticRelevance = clamp(50 * (cosine_similarity + 1), 0, 100)
HybridRelevance   = 0.25 * LexicalRelevance + 0.75 * SemanticRelevance
Eligibility       = (HybridRelevance / 100)^2
SecondaryQuality  = weighted mean of Freshness, Engagement, Source Confidence,
                    Cross-Source Presence, and Novelty
FinalScore        = clamp(0.99 * HybridRelevance
                          + 0.01 * Eligibility * SecondaryQuality
                          - SpamPenalty, 0, 100)
```

The one-percent quality budget was selected on a separate hard-negative tuning set. It prevents
freshness, engagement, source preference, or distribution from reversing a substantial relevance
difference. The normal explanation exposes lexical relevance, semantic relevance, phrase evidence,
query coverage, and the selected strategy; full feature data stays in Search Diagnostics.

Model loading and inference are isolated from the FastAPI event loop. If FastEmbed or the exact
model files are absent, corrupt, or cannot initialize, MIRSAD records the capability state and uses
the lexical formula. Search does not download a model or fail because semantic ranking is unavailable.

Supporting signals do not receive their full nominal weight for a weak lexical candidate:

```text
SupportingFactor = (Relevance / 100)^2
PrePenalty = 0.35 * Relevance
           + SupportingFactor * (all other weighted positive components)
FinalScore = clamp(PrePenalty - SpamPenalty, 0, 100)
```

This makes relevance the gate: popularity, freshness, source preference, or distribution can refine strong matches but cannot rescue a weak match. The score explanation stores the factor, each weighted component, and the pre-penalty value so the UI does not reconstruct the calculation.

## Freshness

```text
lambda = ln(2) / half_life_hours
freshness = 100 * exp(-lambda * age_hours)
```

The default half-life is 48 hours. Future timestamps use zero age; missing timestamps receive 25 rather than being represented as recent.

## Engagement

Each source has its own metric adapter and reference scales. Values use a clamped logarithmic transform based on the platform’s metric names, then average within that adapter. Raw values and normalized engagement are both stored. YouTube views are never directly compared with Hacker News points or GitHub stars.

Social adapters consume only metrics actually returned: X uses likes/reposts/replies/quotes/views; Threads uses available likes/replies/reposts/quotes; Telegram uses views/forwards/reactions/replies; Reddit uses score/comments; YouTube uses views/likes/comments; TikTok uses views/likes/comments/shares/favorites; Instagram uses permitted likes/comments; Mastodon uses favourites/reblogs/replies. Missing metrics do not contribute a synthetic zero.

## Social Reach

Social Reach is optional, deterministic, and separate from Final Score:

```text
diversity = 100 * (1 - exp(-(platform_count - 1) / 2))
SocialReach = clamp(0.80 * Engagement + 0.20 * diversity, 0, 100)
```

It is calculated only for social-source records from normalized public engagement and independent platform diversity. It measures observable distribution/interaction within MIRSAD's collection, not truth, reliability, causality, audience size, or importance.

## Other Signals

- Source Confidence is an editable source preference, not an objective reliability claim.
- Cross-Source Presence is non-zero only for duplicate groups across independent connectors. Repeated posts from one platform do not increase independent platform diversity. It records distribution, not verification.
- Novelty gives an ungrouped/representative record 100 and non-representative duplicate members 40 while retaining every original.
- Spam Penalty transparently covers short content, excessive exclamation, high uppercase ratio, and repeated tracking parameters; it is capped at 20.

## Related Terms

Related terms are document-frequency counts over normalized title/text tokens. URLs and hashtag markers are removed, terms count once per document, tokens shorter than three characters are excluded, and separate basic English/Arabic stopword sets are applied. Normalized query tokens are excluded so the query itself cannot dominate the output. This is descriptive lexical extraction, not generated text.

## Evaluation

`npm run evaluate:search` evaluates 30 deterministic Arabic/English/mixed fixture records against 20 representative queries and a separate hard set of 40 records/16 adversarial queries. Fixtures cover exact/partial matches, irrelevant collisions, duplicate/near-duplicate stories, old/recent items, high-engagement irrelevant records, and low-engagement relevant records.

The versioned result in `reports/search-quality.json` contains standard fixed-denominator and returned-set Precision@5/10 (with legacy `strict` aliases retained for artifact compatibility), MRR, language breakdowns, duplicate/cluster pair checks, score distributions, ranked IDs, and per-query labels. `reports/relevance-improvement.md` compares the frozen legacy/current pipelines. The suite uses production normalization and scoring with a documented deterministic lexical BM25 proxy; it is maintainable regression evidence, not a claim of universal retrieval quality.

`npm run evaluate:holdout` reproduces the frozen lexical baseline over a separately stored
110-document corpus and 16 judgment records. The SHA-256 guarded final hybrid evaluation is stored
in `reports/relevance-recovery-holdout.json`; it is not a tuning input. The separate hard-negative
tuning corpus is in `relevance_tuning_*.json`. Metric definitions are independently unit-tested and
use a fixed Precision@K denominator. The final report in
`reports/relevance-recovery-final.md` records every query, including regressions and weak slices.

## Explanation And Diagnostics

Every score row persists all components, matched terms, penalty, and final value. The Explain Score sheet also shows source/subtype, fetch and publication times, and duplicate group.

The optional Search Diagnostics dialog reads stored per-session data: original/normalized query, variants, sources, connector status/counts/latency, duplicates, unique count, phase timings, and score-component histograms. It is intentionally separate from normal result cards.

Phase 3 diagnostics also retain algorithm versions, production and shadow router orders, calibrated
shadow uncertainty/saturation evidence, and shadow fusion/diversity overlap. These fields explain an
experiment; they do not imply that it influenced production. The System quality view reports
retrieval utility rather than truth, credibility, or live precision.
