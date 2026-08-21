# MAFER Phase 2: Adaptive Federated Search Intelligence

## Executive Assessment

MAFER Phase 2 adds a deterministic planning layer before MIRSAD's existing content
pipeline. It classifies query intent, builds a bounded and provenance-preserving query
lattice, searches local memory before network sources, routes sources by capability and
availability, executes bounded rounds, fuses discovery evidence with weighted reciprocal
rank fusion (RRF), and records explicit uncertainty, marginal-gain, and stop decisions.

The planning benchmark is a separate 20-query action-and-candidate fixture, not a frozen
relevance holdout. Against its baseline, the selected BALANCED plan increased candidate
recall from `0.9400` to `0.9607`, relevant candidate yield from `5.55` to `6.60`, P@5 from
`0.4600` to `0.8600`, MRR from `0.7375` to `1.0000`, and nDCG@10 from `0.7430` to `0.9010`.
This cost `12.75` rather than `10.00` simulated requests per query and two rounds rather
than one. These metrics measure the benchmark's planned candidate evidence, not Internet
latency or a replacement final ranker.

The frozen production ranking, semantic, and clustering files retain their authoritative
hashes. No Phase 2 path changes the `25%` lexical / `75%` semantic strategy, the bounded
semantic top 20, or the `1%` secondary-quality budget.

## Phase-1 Invariants

- Phase 1 acquisition modes, SearXNG boundary, URL validation, discovery memory/cache,
  Common Crawl exact-URL lookup, oEmbed handling, SSRF controls, and fair per-source
  candidate admission remain in place.
- Final ranking continues only after fair per-source lexical opportunity and global
  semantic evaluation. Phase 2 source planning controls retrieval work, not final source
  representation.
- Phase 2 does not force platform diversity and does not convert discovery support into
  truth, credibility, or reliability.
- `ranking.py`: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py`: `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24`
- `clustering.py`: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`

## Intent Fingerprint

`mafer/intent.py` implements an explainable `QueryIntentAnalyzer`. It returns multiple
labels, confidence, evidence, script distribution, quoted segments, token count, query
length, temporal terms, identifier patterns, and ambiguity indicators. Supported labels
include HANDLE, HASHTAG, PERSON_LIKE, ENTITY_LIKE, TOPIC, EVENT_LIKE, EXACT_PHRASE, URL,
DOMAIN, IDENTIFIER, RECENT_INTENT, HISTORICAL_INTENT, AMBIGUOUS, ARABIC, ENGLISH, and
MIXED_LANGUAGE. Heuristic labels remain explicitly probabilistic.

Tests cover common names, ambiguous terms, URLs/domains, exact phrases, scripts, Arabic,
mixed language, handles, hashtags, and identifiers.

## Query Lattice

`mafer/lattice.py` creates deterministic ORIGINAL, NORMALIZED, EXACT,
ARABIC_NORMALIZED, HANDLE, HASHTAG, IDENTIFIER, TRANSLITERATION, ENTITY_ALIAS, and
EVIDENCE_EXPANDED nodes. Every node retains a stable ID, parent, transformation, intent,
language, confidence, drift risk, creation round, eligible capabilities, and reason.

ORIGINAL is immutable and always first. Variant counts are hard-bounded by the selected
budget. Exact identifiers are not semantically rewritten. The standalone lattice ablation
reduced P@5 from `0.6400` after intent routing to `0.5700` and Recall@10 from `0.9400`
to `0.7965`; this is evidence that variants
must be fused and selected rather than treated as equally useful raw requests. Weighted
RRF resolves that incompatibility without altering final MIRSAD scoring.

## Arabic Processing

The lattice preserves original Arabic, including diacritics, alongside conservative
normalized evidence. `وِزَارَةُ التَّخْطِيط` therefore retains its exact original form and
may also use `وزارة التخطيط`. Arabic names can receive a small bounded transliteration
set only when PERSON_LIKE or ENTITY_LIKE evidence exists. Generic topics are not
transliterated.

On five Arabic planning cases the selected strategy achieved P@5 `0.7600`, P@10
`0.4800`, MRR `1.0000`, nDCG@10 `0.7972`, and candidate recall `0.8429`. This is lower
than English candidate recall and remains a measured limitation rather than a hidden
claim of parity.

## Identifier Search

CVE, GHSA, CWE, commit hashes, package/repository identities, domains, URLs, and handles
receive IDENTIFIER evidence. Literal preservation precedes any other variant. CVE years
do not incorrectly imply historical intent. Four identifier benchmark cases achieved
P@5 `0.9500`, P@10 `0.5750`, MRR `1.0000`, and candidate recall `1.0000`.

## Temporal Intent

The analyzer distinguishes TIME_CRITICAL, RECENT_PREFERRED, TIME_NEUTRAL, and HISTORICAL.
Explicit request filters override heuristics. The planner uses temporal intent for source
utility, cache policy, discovery freshness, and historical eligibility only; it does not
change the frozen freshness score. Common Crawl remains restricted to configured exact-URL
historical lookup and is not advertised or called as arbitrary keyword search.

## Resource Router

`mafer/routing.py` scores capability match, query-intent fit, language fit, temporal fit,
observed historical yield, unique yield, current health, current availability, latency,
duplicate rate, and novelty potential. Routing derives from connector metadata rather
than frontend platform assumptions. Explicit source selection remains authoritative;
automatic selection is used only when the user chooses the automatic source behavior.

## Web Engine Router

SearXNG engines retain historical target-domain precision, canonical yield, unique yield,
latency, duplicate rate, timeout rate, and rate-limit rate separately from current state.
Current states include healthy, degraded, rate limited, CAPTCHA blocked, and temporarily
unavailable. CAPTCHA/429/timeout outcomes enter bounded cooldown; later success recovers
the engine. No proxy rotation, login automation, CAPTCHA solving, or retry hammering was
added.

## Current Availability Separation

Resource utility stores `long_term_utility` independently from `current_availability`.
A temporarily blocked engine suppresses an immediate request without teaching the planner
that X or Threads are inherently useless. Tests cover healthy, unavailable, rate-limited,
and externally blocked distinctions. External blocking is excluded from successful
zero-result evaluation.

## Local Memory

Round 0 queries content FTS, Phase 1 discovery memory, and high-confidence alias edges.
Returned records are marked as local evidence and do not masquerade as fresh external
coverage. Current/time-critical intent continues to external retrieval even when memory
has results. The local-memory ablation increased relevant candidate yield from `5.55` to
`6.55` and candidate recall from `0.9400` to `0.9524` in the benchmark.

## Search Rounds

The service executes bounded concurrent connector tasks with a monotonic deadline. Round
1 uses original and safest variants with the strongest available resources. Round 2 can
add safe resources or variants. Round 3 is reserved for justified evidence expansion or
supported historical work. Normal automatic retrieval is capped at two rounds unless the
third-round prerequisites exist. Partial results survive cancellation or connector failure.

## Budgets

The implemented profiles bound wall time, rounds, source calls, engine calls, variants,
discovered URLs, normalized candidates, semantic candidates, and historical calls:

| Profile | Wall time | Rounds | Source calls | Engine calls | Variants | URLs | Normalized | Semantic | Historical |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FAST | 5 s | 1 | 6 | 8 | 3 | 80 | 120 | 20 | 0 |
| BALANCED | 12 s | 2 | 12 | 20 | 6 | 200 | 300 | 20 | 0 |
| DEEP | 25 s | 3 | 20 | 36 | 10 | 400 | 600 | 20 | 2 |

The semantic bound is unchanged at 20. Budget tests verify actual work limits, not labels.

## Weighted RRF

`mafer/fusion.py` computes discovery-level weighted reciprocal-rank fusion. Variant
confidence and bounded resource/engine utility weight independent ranked discovery paths;
raw engine scores are never compared. RRF affects only canonical candidate priority before
content admission. It neither enters nor replaces final lexical/semantic scoring.

Adding RRF to intent, lattice, and memory increased P@5 from `0.7000` to `0.8800`, MRR
from `0.9750` to `1.0000`, nDCG@10 from `0.8010` to `0.9079`, while requests stayed at
`10.00` per query.

## Evidence Completeness

`mafer/evidence.py` records canonical URL, indexed title/snippet, full text, author,
publication timestamp, and official-embed metadata as distinct evidence. It labels level
and missing fields without turning unknowns into zero or fabricating content. The live
Reddit WEB_INDEX observation recorded a moderate completeness score of `0.46` for real
URL/title/snippet evidence.

## Gated Expansion

Pseudo-relevance expansion requires coherent support from at least three records and two
sources, accepts only distinctive stable handles/entities/identifiers, retains the original
query, and records support, confidence, and drift risk. It is disabled for identifiers and
ambiguous queries. The benchmark showed no gain after enabling it, so it remained dormant
and did not add requests or variants. It is retained as a gated path because the no-op is
the intended safe behavior when evidence is insufficient.

## Topic Drift

Expansion rejects generic, query-replacing, single-source, or weakly supported terms.
Tests include tempting high-frequency terms from irrelevant results and verify rejection.
No external synonym or LLM expansion exists.

## Entity Alias Graph

`entity_alias_edges` stores relationship type, source, support count, first/last seen, and
confidence. Only edges with at least two supporting observations and high confidence can
become low-risk lattice variants. Similar names and embedding similarity alone cannot
merge identities. Tests cover supported aliases and same-name false positives.

## Uncertainty

`mafer/assessment.py` returns LOW, MEDIUM, or HIGH with reasons based on yield,
lexical/semantic disagreement, variant disagreement, source paths, rank margins, evidence
completeness, and single-engine dependence. The post-ranking assessment is recorded in the
trace but does not modify ranking. In the one-round ablation, adding uncertainty changed no
quality or request metric because no escalation decision was available; this is reported
as a neutral result, not an artificial benefit.

## Marginal Evidence Gain

Every round records new canonical URLs, admitted candidates, platforms, stories, aliases,
requests, elapsed time, and an explainable gain value. The planner stops when later rounds
add negligible evidence. A live FAST Reddit observation recorded four discoveries, three
admitted candidates, one platform, and marginal gain `2.16`.

## Stop Logic

Search traces use SATISFIED, LOW_MARGINAL_GAIN, MAX_ROUNDS, TIME_BUDGET, REQUEST_BUDGET,
SOURCE_EXHAUSTION, NO_AVAILABLE_SOURCES, or USER_LIMIT. A deadline-expired source is
cancelled and healthy partial results remain. Tests cover low gain, limits, external
exhaustion, and explicit selection completion.

## FAST / BALANCED / DEEP

| Mode | P@5 | P@10 | MRR | Candidate recall | Useful URLs | Requests | Simulated external latency | Rounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FAST | 0.7800 | 0.4900 | 1.0000 | 0.7480 | 4.95 | 6.00 | 2,105 ms | 1.00 |
| BALANCED | 0.8600 | 0.5950 | 1.0000 | 0.9607 | 6.60 | 12.75 | 4,557.5 ms | 2.00 |
| DEEP | 0.8600 | 0.5950 | 1.0000 | 0.9607 | 6.60 | 12.75 | 4,557.5 ms | 2.00 |

DEEP did not spend its third round because the benchmark supplied no justified expansion
or historical evidence need. This demonstrates stop logic rather than an assertion that
DEEP is always more expensive. The displayed UI wording is therefore “wider multi-round
discovery,” not complete search.

## Source Fairness

Phase 1's deterministic round-robin admission across per-source lexical queues remains
immediately before the frozen semantic stage. Phase 2 adds no final source quota. Tests
shuffle connector request order and completion delays, verify stable admitted identities,
and verify one source cannot consume every semantic opportunity merely by completing
first. Final top results may still come from one source when relevance justifies it.

## Benchmark

The fixture contains 20 difficult Arabic, English, and mixed queries covering handles,
people, entities, topics, hashtags, identifiers, events, exact phrases, historical intent,
and ambiguity. It contains hard collisions and explicit resource/variant action labels.
Fixture SHA-256: `08aaeb23023ae1015a397c979ab39f4767251700ec0e552dbfc89fad2043dca9`.
The fresh evaluator runtime was `68.07 ms`. The JSON artifact is
`reports/mafer-phase2-benchmark.json`.

This benchmark is not the frozen ranking evaluation. Its latency values model connector
work and are explicitly labeled simulated external latency. Live Internet timings and
local engine timings are reported separately.

## Ablation Study

| Strategy | P@5 | P@10 | MRR | Recall@10 | nDCG@10 | Candidate recall | Useful URLs | Requests | Rounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BASELINE | 0.4600 | 0.5550 | 0.7375 | 0.9400 | 0.7430 | 0.9400 | 5.55 | 10.00 | 1.00 |
| + Intent routing | 0.6400 | 0.5550 | 0.8917 | 0.9400 | 0.8384 | 0.9400 | 5.55 | 10.00 | 1.00 |
| + Query lattice | 0.5700 | 0.4600 | 0.8917 | 0.7965 | 0.7347 | 0.9400 | 5.55 | 10.00 | 1.00 |
| + Local memory round 0 | 0.7000 | 0.5200 | 0.9750 | 0.7746 | 0.7908 | 0.9524 | 6.55 | 10.00 | 1.00 |
| + Weighted RRF | 0.8800 | 0.5900 | 1.0000 | 0.8690 | 0.9079 | 0.9524 | 6.55 | 10.00 | 1.00 |
| + Uncertainty | 0.8800 | 0.5900 | 1.0000 | 0.8690 | 0.9079 | 0.9524 | 6.55 | 10.00 | 1.00 |
| + Multi-round escalation | 0.8600 | 0.5950 | 1.0000 | 0.8773 | 0.9010 | 0.9607 | 6.60 | 12.75 | 2.00 |
| + Gated evidence expansion | 0.8600 | 0.5950 | 1.0000 | 0.8773 | 0.9010 | 0.9607 | 6.60 | 12.75 | 2.00 |

The lattice regression before RRF and the slight P@5 reduction in the wider two-round
strategy are retained honestly. The selected BALANCED behavior favors higher candidate
recall and P@10 over the one-round RRF peak P@5, while staying bounded.

## Arabic Results

Five cases: P@5 `0.7600`, P@10 `0.4800`, MRR `1.0000`, Recall@10 `0.7429`,
Recall@20 `0.8206`, nDCG@10 `0.7972`, candidate recall `0.8429`, `14.00` requests,
and two rounds per query. Arabic is the weakest candidate-recall segment and should be
monitored with independent future planning fixtures; Phase 2 does not retune final Arabic
ranking.

## English Results

Thirteen cases: P@5 `0.8769`, P@10 `0.6231`, MRR `1.0000`, Recall@10 `0.9101`,
Recall@20 `1.0000`, nDCG@10 `0.9267`, candidate recall `1.0000`, and `11.923` requests.

## Mixed Results

Two cases: P@5 `1.0000`, P@10 `0.7000`, MRR `1.0000`, Recall@10/20 `1.0000`,
nDCG@10 `0.9932`, candidate recall `1.0000`, and `15.00` requests. The sample is small,
so it proves deterministic handling rather than broad population performance.

## Handle / Person Results

Handle cases achieved P@5 `0.8000`, MRR `1.0000`, and candidate recall `1.0000`.
Person-like cases achieved P@5 `0.8000`, MRR `1.0000`, and candidate recall `0.9166`.
The router preserves long-term X/Threads utility even when current web engines are blocked.

## Identifier Results

Four cases achieved P@5 `0.9500`, P@10 `0.5750`, MRR `1.0000`, Recall@10/20
`1.0000`, nDCG@10 `0.9962`, and candidate recall `1.0000`. Exact preservation and
identifier-capable source routing produced the strongest class result.

## Latency

Fresh local deterministic benchmark with three concurrent 50 ms fixture connectors, 12
runs: median wall time `198.99 ms`, p95 `230.92 ms`, median connector time `57.55 ms`,
persistence `18.55 ms`, deduplication `22.55 ms`, ranking `75.82 ms`, and clustering
`6.64 ms`. Frozen ranking/deduplication/clustering code was not optimized in this phase.

Scaling observations: normalization/ranking were `0.30/5.20 ms` at 100 records,
`0.61/8.94 ms` at 200, `3.13/44.35 ms` at 1,000, `16.19/226.95 ms` at 5,000, and
`32.56/434.71 ms` at 10,000. Deduplication/clustering were separately measured at bounded
100 (`80.33/5.78 ms`) and 200 (`344.69/13.56 ms`) workloads.

One low-volume live Reddit WEB_INDEX FAST search completed in `673 ms`: connector
`651.94 ms`, persistence `5.51 ms`, deduplication `0.31 ms`, ranking `2.82 ms`,
clustering `3.06 ms`. Semantic was deliberately disabled only for this transport/planning
observation and is not presented as a semantic performance measurement.

## Request Efficiency

FAST used `6.00` requests and one round versus BALANCED `12.75` requests and two rounds.
BALANCED gained `1.65` useful URLs and `0.2127` candidate recall over FAST in the fixture.
DEEP spent no additional request because uncertainty and marginal gain did not justify a
third round. Web-engine and source-call budgets are consumable across rounds rather than
reset per round.

Time-to-first evidence injection measured a fast source at `37.95 ms`, a medium source at
`98.17 ms`, and a slow failure at `188.41 ms`; the current REST response remains
non-streaming and returned the usable partial result set at total completion (`980.23 ms`).
The trace exposes individual progress/failure rather than claiming incremental streaming.

## Failure Injection

Deterministic tests cover SearXNG unavailable, CAPTCHA-blocked engines, 429, timeout,
partial WEB_INDEX availability, Bluesky pagination failure, Mastodon auth requirement,
YouTube API failure, Common Crawl unavailable, semantic fallback, empty/large memory,
malformed discovery records, random completion order, and request deadlines. Healthy
sources remain usable, outcomes retain blocked/error/no-result distinctions, and no
failure creates fabricated metrics.

The existing GDELT total-budget evidence remains bounded: two injected failed attempts
took about `20 ms` each plus a `250 ms` backoff for total connector times of `291.32 ms`
and `292.16 ms`; the circuit then opened and returned in `0.007 ms`.

## Security

Query lattice values remain search text. They cannot change SearXNG, Common Crawl,
oEmbed, connector hosts, URL schemes, private-IP restrictions, or redirect policy. Phase
1 fixed/allowlisted destinations and canonical URL validation remain authoritative. No
frontend secret fields, arbitrary backend fetch, raw embed HTML execution, CAPTCHA bypass,
login automation, or external LLM was introduced.

## External Limitations

- Normal local configuration currently has SearXNG disabled; `verify-sources` reports that
  state honestly.
- A temporary low-volume local SearXNG run produced three real Reddit WEB_INDEX records
  from four matching normalized candidates in `673 ms`. DuckDuckGo returned 10 target
  results; Brave was rate limited and Startpage reported CAPTCHA.
- X and Threads health paths were reachable in that temporary setup, but no successful
  live target records were claimed. Current upstream blocking remains external evidence,
  not a negative long-term source prior.
- Common Crawl remains exact-URL historical metadata lookup, not historical keyword search.
- The API does not stream the first completed source; useful partial results are returned
  after the bounded round completes, with per-source progress/telemetry visible.

## Regressions

- Fresh validation passed: backend `184/184`; frontend `18/18`; focused Phase 2 `26/26`;
  Playwright `11` passed with `2` deliberately skipped opt-in live-session cases; Ruff,
  Oxlint, TypeScript, production build, doctor, source verification, reset/database
  integrity, FTS lifecycle, and localhost startup smoke all passed.
- New deterministic coverage includes intent, ambiguity, Arabic/mixed queries, identifier
  preservation, bounded lattices, transliteration, temporal intent, resource/engine
  routing, availability separation, circuit breaking, RRF, memory round 0, uncertainty,
  marginal gain, stop reasons, gated expansion/drift, aliases, budgets, source/completion
  order invariance, external-block classification, and partial failure.
- Browser coverage confirms the shadcn mode selector, automatic source behavior, localized
  diagnostics, Arabic direction switching, and state retention. No additional component
  system was introduced.
- Bounded backend memory observations across 31 repeated/large searches ranged from
  `708,996` to `711,836 KiB` (`2,840 KiB` span). Browser observation decreased from
  `24,365,304` bytes / 3,792 nodes to `23,288,980` bytes / 1,536 nodes after stress.
  These are bounded observations, not a formal proof of leak freedom.
- Startup evidence: API `/api/v1/health` returned `{"status":"ok"}`, frontend `/search`
  returned HTTP `200`, and neither runtime log contained a traceback, error, exception, or
  unhandled rejection. SQLite reported `integrity=ok`, zero foreign-key violations, and a
  synchronized empty post-reset content/FTS count of `0/0`.

MAFER INTELLIGENCE CORE VERIFIED
