# MAFER Phase 3 Final Verification

Date: 2026-08-10  
Application: MIRSAD `1.0.0-rc1`  
Phase: Calibration, Arabic Recovery, Shadow Learning, And Production Gate

## Executive Assessment

Phase 3 established a local, privacy-conscious evidence and shadow-evaluation system without changing
the verified production retrieval or ranking path. Production remains the deterministic Phase 2
planner and the frozen 25% lexical / 75% MiniLM fusion over at most 20 semantic candidates with a 1%
secondary-quality budget. No adaptive component was promoted.

The new independent holdout exposed real weaknesses in Phase 2 stop calibration: all 18 production
cases were labeled LOW uncertainty, three stopped prematurely, and five ran an unnecessary additional
round. The shadow saturation policy reduced both judged error counts to zero on this controlled
holdout, but the 18-query sample produced bootstrap intervals that include zero for every aggregate
retrieval delta. Arabic candidate recall also remained unchanged. The correct production decision is
therefore to keep Phase 2 and continue collecting shadow evidence.

## Phase-2 Baseline

The baseline was recorded before production changes in `reports/mafer-phase3-baseline.md`.

| Frozen component | SHA-256 |
| --- | --- |
| `domains/ranking.py` | `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4` |
| `domains/semantic.py` | `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24` |
| `domains/clustering.py` | `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63` |

Final validation reproduced all three hashes. Phase 2 BALANCED historical evidence was P@5 `0.8600`,
P@10 `0.5950`, MRR `1.0000`, candidate recall `0.9607`, `6.60` useful URLs/query,
`12.75` requests/query, and `2.0` rounds/query. Arabic candidate recall was `0.8429` versus English
`1.0000`.

## New Independent Evaluation Design

The development set contains 16 cases: 8 Arabic, 7 English, and 1 mixed-language. The frozen holdout
contains 18 different cases: 6 Arabic, 10 English, and 2 mixed-language. It covers person/common-name
collisions, organizations, diacritized exact phrases, spelling variants, handles, hashtags, CVE/GHSA
and commit identifiers, recent and historical events, ambiguous terms, long topics, cross-platform
duplicates, and partial upstream outage.

Each case records judged possible relevant count, useful sources/variants, two bounded retrieval rounds,
stage-level relevant counts, relevant ranks, observable uncertainty inputs, and an independently declared
optimal stopping round. This is a controlled search-planning evaluation, not a live-network benchmark
and not a substitute for future explicit operator judgments.

## Holdout Integrity

- Development: `cf5be21e8d87e57599787a12472a0358fc59a67c850dd1f4dc84758c441ebae8`.
- Frozen holdout: `50b06e990e39e41995893b4de288553d16d4f575ca2d825554039004b23b5ca2`.
- The holdout was evaluated once after development calibration and was not edited or rerun for tuning.
- `test_phase_three_holdout_is_frozen_and_independent` enforces the hash, unique queries, size, and
  Arabic/mixed representation.
- `reports/mafer-phase3-confidence.json` performs read-only paired bootstrap analysis over the already
  generated holdout artifacts; it does not rerun ranking.

## Uncertainty Calibration

Production assigned LOW uncertainty to all development and holdout cases, so its categories had no
empirical ordering. The shadow model uses candidate yield, independent sources, remaining healthy useful
sources, variant agreement, lexical/semantic disagreement, rank margin, evidence completeness,
single-engine dependence, degradation, language/query class, and gain trajectory.

On development, shadow LOW cases had candidate recall `0.9254` and the one HIGH case `0.8000`. On the
holdout, shadow LOW cases had candidate recall `0.9224` and the one HIGH case `0.8000`. Direction is
sensible, but one HIGH sample is insufficient calibration evidence for promotion. A trace wording bug
that described HIGH uncertainty as “high confidence” was corrected to “high retrieval uncertainty” and
covered by regression assertion; it never affected decisions or metrics.

## Stop Calibration

| Set | Strategy | Premature stops | Unnecessary rounds | Missed admitted gain | Correctly avoided requests |
| --- | --- | ---: | ---: | ---: | ---: |
| Development | Phase 2 production | 1/16 | 4/16 | 3 | 10 |
| Development | Phase 3 shadow | 0/16 | 0/16 | 0 | 23 |
| Holdout | Phase 2 production | 3/18 | 5/18 | 9 | 10 |
| Holdout | Phase 3 shadow | 0/18 | 0/18 | 0 | 25 |

Holdout false stops were a recent event, a historical query, and a duplicate-heavy partial-outage case.
The policy does not always add a round: it stopped several hashtag, mixed entity, identifier, and exact
queries one round earlier. Hard time, request, and round budgets remain authoritative. No production
stop threshold changed.

## Arabic Retrieval Loss Funnel

Nine Arabic-inclusive development cases produced this funnel:

```text
possible relevant       53
discovered              50
canonical               50
candidate admitted      47
semantic opportunity    47
top 10                  45
```

Losses were 3 at source coverage/discovery, 0 at canonicalization, 3 at candidate admission, 0 at
semantic opportunity, and 2 after final ordering. The primary Arabic weakness is therefore upstream
coverage/admission, not lack of semantic opportunity. This prevents an unsupported claim that replacing
the model alone recovers Arabic retrieval.

## Arabic Query Improvements

Development experiments retained original diacritized text alongside normalized/exact forms and
evaluated bounded transliteration only for person/entity-like queries. Original, exact, normalized, and
Arabic-normalized variants were useful in different cases; generic topic transliteration was not added.
No new production variant was promoted because the shadow plan did not improve Arabic candidate recall
on development (`0.8768` both) or holdout (`0.8595` both). Broad synonyms and more aggressive pseudo-
relevance expansion remain disabled.

## Arabic Model Experiments

Both evaluated models are local and declared Apache-2.0 by their official model cards:
[MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) and
[MPNet](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2).

| Frozen semantic sample | MiniLM | MPNet shadow |
| --- | ---: | ---: |
| Overall P@5 | 0.3778 | 0.3889 |
| Overall MRR | 0.7565 | 0.8611 |
| Overall nDCG@10 | 0.8179 | 0.8924 |
| Arabic P@5 | 0.3333 | 0.3667 |
| Arabic MRR | 0.5474 | 0.7500 |
| Arabic Recall@10 | 0.8333 | 1.0000 |
| Arabic nDCG@10 | 0.6480 | 0.8178 |

Paired MPNet-minus-MiniLM intervals were P@5 `+0.0111 [0.0000, 0.0333]`, MRR
`+0.1046 [0.0278, 0.1972]`, and nDCG@10 `+0.0745 [0.0045, 0.1620]`. MPNet was not
promoted: this was an isolated semantic sample rather than the integrated lexical/semantic pipeline,
P@5 improvement was small, its measured peak RSS delta was about 1.76 GiB versus 596 MiB, its local
cache was 1.1 GiB versus 241 MiB, and document encoding was about 3.4 times slower.

## Adaptive Fusion Experiments

The development-derived shadow mapping increased lexical weight only for inspectable identity classes
and kept topics at 25%. On the frozen synthetic fusion profiles, production versus query-aware shadow
was P@5 `0.5889 -> 0.9333` and nDCG@10 `0.8385 -> 0.9927`. Paired deltas were P@5
`+0.3444 [0.2111, 0.4667]` and nDCG@10 `+0.1542 [0.0949, 0.2139]`.

It was not promoted because the fusion fixture uses controlled class profiles rather than records
retrieved and scored by the complete production pipeline. P@10, MRR, and Recall@10 interval lower
bounds were zero. Changing the frozen 25/75 strategy therefore requires a new integrated independent
evaluation, not this diagnostic experiment.

## Feedback System

Local outcome tables and APIs record search execution, opened/bookmarked results, explicit relevant/not
relevant judgments, reformulation, zero-result, and source-failure events. The server verifies that a
content record belongs to the stated search session and derives rank, source, acquisition mode, query
class, and algorithm versions; the browser cannot provide authoritative values. Payload size and type
are bounded. Result cards provide optional localized shadcn actions. `RESULT_OPENED` has no explicit
judgment and is never counted as relevance.

## Source Utility Learning

The shadow learner is scoped to `(query_class, source)`, requires five observations, uses a 30-day
half-life, deduplicates explicit judgments by content item, requires at least three explicit items before
including them, and clamps adjustments to `[-8,+8]`. Reward combines admitted/returned yield,
unique/returned yield, top-k/admitted contribution, duplicate cost, bounded latency, and failures. Raw
result count, engagement, popularity, source confidence, truth, and credibility are not rewards.

## Engine Utility Learning

SearXNG observations are scoped to engine, target platform, and query class. They retain request and
availability state, target-domain precision, canonical/unique/later-judged yield, latency, 429, CAPTCHA,
and timeout. Current availability remains the circuit-breaker concern; it is not converted into a
permanent negative source prior. No engine learner was promoted.

## Shadow Router

`mafer-shadow-router-v3.0` applies only bounded learned adjustments to the Phase 2 utility ordering and
uses source key as a deterministic tie-breaker. It records production and shadow order, adjustment, and
whether the order changed. It cannot alter connector calls or visible results. Empty or malformed
learning history returns the deterministic Phase 2 route.

## Reward Design

Explicit judgments are stronger than clicks. Clicks are interaction-only. Retrieval reward favors
unique admitted/top-k yield at bounded request/latency/duplicate cost; it excludes engagement and source
confidence. Minimum evidence, per-class isolation, time decay, latest-judgment semantics, and the +/-8
clamp limit poisoning and instability. This is a conservative heuristic, not a trained credibility model.

## Adaptive Stability

Tests prove deterministic shadow fusion/diversity under reversed input, bounded learning adjustment,
minimum evidence, malformed/empty-history fallback, and production connector-completion/order
invariance. Shadow strategies only observe completed production evidence, preventing feedback or model
failure from corrupting a user-visible search.

## Evidence Graph

The local graph records content, canonical URL, source, author handle, hashtag, story, and query nodes
with observed `discovered_by`, `links_to`, `published_on`, `mentions`, and algorithmic `same_story`
edges. Tests prohibit identity/causality/truth relationships. It assists local provenance exploration and
does not establish factual correctness or personal identity.

## Search Saturation

Shadow stopping considers round-to-round unique/admitted gain, available coverage, uncertainty, and hard
budgets. Unique and admitted gain both below 15% of the previous round produces
`LOW_MARGINAL_GAIN`; no healthy useful source produces `SOURCE_EXHAUSTION`; budgets override adaptive
evidence. The holdout average changed from `1.667` to `1.556` rounds while fixing both premature and
unnecessary judged stops. This remains shadow evidence.

## FAST / BALANCED / DEEP

Phase 2 profiles remain unchanged. On the historical planning fixture, FAST used 6 requests and 1 round
with candidate recall `0.7480`; BALANCED used 12.75 requests and 2 rounds with `0.9607`; DEEP matched
BALANCED because no third round was justified. Phase 3 does not force DEEP to spend more. The new
holdout shows specific recent/historical/outage cases where a second round adds value, but does not
contain evidence that a third round is warranted.

## Production vs Shadow

| Frozen holdout | Phase 2 production | Phase 3 shadow | Delta |
| --- | ---: | ---: | ---: |
| P@5 | 0.6444 | 0.7222 | +0.0778 |
| P@10 | 0.4556 | 0.5000 | +0.0444 |
| MRR | 0.9722 | 1.0000 | +0.0278 |
| Recall@10 | 0.7906 | 0.8644 | +0.0738 |
| Recall@20 / candidate recall | 0.8307 | 0.9156 | +0.0849 |
| nDCG@10 | 0.7862 | 0.8559 | +0.0697 |

Paired 95% bootstrap intervals for P@5 `[0.0000,0.1667]`, P@10 `[0.0000,0.1000]`,
MRR `[0.0000,0.0833]`, Recall@10 `[0.0000,0.1587]`, and nDCG@10
`[0.0000,0.1428]` all include zero. Shadow retrieval therefore remains unpromoted.

## Promotion Decisions

No Phase 3 component was promoted. The active verified snapshot remains Phase 2; the active experimental
snapshot contains only shadow versions. No promotion-candidate or previous-production snapshot exists
because no promotion transaction occurred. This prevents a meaningless rollback from being offered.

## Rejected Experiments

- Adaptive router: retained in shadow; no live explicit-judgment volume and no independent routing gain.
- Calibrated uncertainty/stop: retained in shadow; promising false-stop evidence but small categorical
  sample and aggregate intervals include zero.
- Arabic MPNet expert: retained as offline shadow evidence; resource cost and incomplete integrated proof.
- Query-aware fusion: retained in shadow; strong controlled-profile result but not a full-pipeline proof.
- Near-tie diversity: rejected for promotion; P@5 was `0.9222` versus fusion `0.9333`, with delta
  `-0.0111 [-0.0444,0.0222]` and no meaningful nDCG@10 gain.
- Gated expansion: dormant; Phase 2 measured no gain and Phase 3 added no evidence to justify requests or
  topic-drift risk.

## Final Ablation

Metrics from different datasets are not directly compared as if they were one leaderboard.

| State | Evaluation | P@5 | P@10 | MRR | Recall@10 | Candidate recall | Requests/query |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original pre-Phase-2 planning baseline | Phase 2, 20 queries | 0.4600 | 0.5550 | 0.7375 | 0.9400 | 0.9400 | 10.00 |
| MAFER Phase 1 | No separate judged planning benchmark | not comparable | not comparable | not comparable | not comparable | not comparable | not comparable |
| MAFER Phase 2 deterministic | Phase 2, 20 queries | 0.8600 | 0.5950 | 1.0000 | 0.8773 | 0.9607 | 12.75 |
| Phase 3 production configuration | Frozen Phase 3, 18 queries | 0.6444 | 0.4556 | 0.9722 | 0.7906 | 0.8307 | 8.33 |
| Phase 3 calibrated shadow | Frozen Phase 3, 18 queries | 0.7222 | 0.5000 | 1.0000 | 0.8644 | 0.9156 | 8.33 |

Phase 1 has source-cap/order-invariance evidence but no independently comparable judged P@K artifact;
inventing a score would be misleading.

## Arabic Results

Frozen production and shadow Arabic metrics were identical: P@5 `0.6333`, P@10 `0.4667`, MRR
`1.0000`, Recall@10 `0.8024`, Recall@20/candidate recall `0.8595`, and nDCG@10
`0.7975`. This is the key reason no adaptive retrieval strategy was promoted. Arabic upstream
discovery/admission remains the principal weakness.

## English Results

Frozen English production versus shadow: P@5 `0.6600 -> 0.8000`, P@10
`0.4400 -> 0.5200`, MRR `0.9500 -> 1.0000`, Recall@10 `0.7616 -> 0.8945`,
candidate recall `0.7995 -> 0.9524`, and nDCG@10 `0.7685 -> 0.8939`.

## Mixed Results

The two mixed-language holdout cases were unchanged: P@5 `0.6000`, P@10 `0.5000`, MRR
`1.0000`, Recall@10/20 and candidate recall `0.9000`, and nDCG@10 `0.8409`. The sample
is too small for a promotion claim.

## Person / Entity / Handle

Person P@5 was `0.4667`, candidate-level Recall@20 `0.8111`; entity P@5 was `0.6667`,
Recall@20 `0.9524`; handle P@5 was `0.8000`, Recall@20 `1.0000`. Production and
shadow retrieval were identical in these slices. Common-name collision remains the weakest identity case.

## Exact Phrase

The two exact-phrase cases remained P@5 `0.8000`, P@10 `0.5000`, MRR `1.0000`, and
Recall@20 `0.9166` for both production and shadow retrieval. The diacritized Arabic case still lost one
item at discovery; exact original text was preserved and no post-holdout normalization tuning occurred.

## Identifier

Two identifier cases remained P@5 `0.9000`, MRR/Recall@10/20 `1.0000` for production and
shadow. Exact identifiers continue to bypass semantic rewriting. Query-aware fusion stays shadow despite
this expected lexical-strength result.

## Topic / Event

Topic retrieval was unchanged at P@5 `0.8000`, P@10 `0.6000`, Recall@10 `0.8541`, and
Recall@20 `0.9166`. Event retrieval exposed stop-calibration weakness: production P@5 `0.2000` and
Recall@20 `0.2976` versus shadow `0.7000` and `0.7619`. Only two event queries support those values,
so the segment is a strong reason to continue shadow observation, not sufficient promotion evidence.

## Performance

- Phase 3 development evaluator: `0.36 s` wall clock and `75,268 KiB` maximum RSS.
- Holdout simulated production/shadow latency: `1457/1430 ms` mean; network was not involved.
- MiniLM: `536.84 ms` warm initialization, `2.7865 ms/item` document encoding,
  `2.5626 ms` query encoding, `610,668 KiB` measured peak RSS delta, 241 MiB local cache.
- MPNet: `981.10 ms` warm initialization, `9.4811 ms/item` document encoding,
  `8.0549 ms` query encoding, `1,845,852 KiB` peak RSS delta, 1.1 GiB local cache. Initial model
  download/cold preparation was observed separately and is not reported as search latency.
- Final Playwright bounded browser observation: heap `24,428,216 -> 23,367,456` bytes and DOM
  nodes `4037 -> 1536`; this is bounded observation, not a formal leak proof.

## Requests

Controlled development production/shadow used `9.06/8.50` requests/query and `1.75/1.56`
rounds/query. Frozen holdout used `8.33/8.33` requests/query and `1.67/1.56` rounds/query.
Shadow made additional calls on the three false-stop cases and avoided calls on several already-saturated
cases, rather than universally increasing work. These are fixture costs, not live Internet timings.

## Failure Injection

The deterministic suites cover empty/malformed learning history, SearXNG unavailable/429/timeout/all-
engine failure, engine cooldown/recovery, external blocking versus zero results, partial web discovery,
Bluesky later-page 403, Mastodon auth-required/timeout/multi-instance partial failure, wall-clock budget
cancellation, malformed discovery payload, Common Crawl bounds, missing semantic model and lexical
fallback, database reset, duplicate-heavy input, and connector completion-order invariance. Healthy
results remain isolated from failed sources.

## Security

Outcome APIs accept only bounded event enums/session/content IDs/context, resolve authoritative fields
server-side, and use parameterized SQLAlchemy queries. Phase 3 makes no outbound fetch target and cannot
weaken existing allowlists/SSRF controls. No external LLM, external analytics, login automation, CAPTCHA
bypass, cookies, proxy rotation, or arbitrary URL fetch was added. Search and ranking secrets remain
backend-only.

## Privacy

Search outcomes, explicit judgments, utility observations, shadow comparisons, configuration snapshots,
and evidence graph remain in local SQLite. No personal profile is constructed. Clicks remain distinct
from judgments. Clear-history/reset actions remove local learning observations as documented; reset also
recreates the verified/experimental configuration slots.

## Rollback

The configuration repository supports verified, experimental, promotion-candidate, and previous-
production slots. The tested one-step operation archives the current verified snapshot, restores the
previous configuration, and leaves content count unchanged. Because no strategy was promoted, the live
database intentionally contains only active `verified_production` and `experimental` slots. Code-level
algorithm changes still require normal source deployment rollback; the snapshot mechanism covers
versioned adaptive configuration.

## Validation

- Backend: `193 passed`.
- Frontend: `6` files, `21 passed`.
- Playwright: `11 passed`, `2` opt-in live cases skipped; route, RTL/LTR, 20-switch stress, portals,
  accessibility, stale request, export/history/bookmark/settings, and bounded memory workflows passed.
- One initial combined Playwright invocation hit a 60-second web-server readiness timeout; direct Vite
  startup and the fresh isolated full rerun passed. No application exception was present.
- Ruff, oxlint, TypeScript, and Vite production build passed; Vite built 2,769 modules.
- `npm run doctor`: all required checks PASS; SearXNG disabled WARN.
- `npm run verify-sources`: Bluesky, Hacker News, GitHub, YouTube, and Mastodon public mode PASS;
  optional/restricted sources WARN without application failure or secret output.
- `npm run reset-db`: passed. SQLite `integrity_check=ok`, zero FK violations, empty synchronized FTS,
  active snapshots `experimental,verified_production`.
- Elevated same-session startup smoke: `start.sh`, API health, quality API, HTML dashboard, log scan, and
  `stop.sh` passed on localhost. Quality output exposed versions/states but no secrets.
- Frozen production and holdout hashes passed after all changes.

## Remaining Limitations

- Arabic candidate loss remains primarily at external discovery/source coverage and candidate admission.
- Uncertainty ordering has only one HIGH case in each new split; more independent judged observations are
  required before categorical calibration can be claimed robust.
- Query-aware fusion evidence is controlled-profile evidence, not an integrated full-pipeline holdout.
- MPNet resource cost is too high for the measured P@5 delta and it remains an offline shadow option.
- Live utility learning has no meaningful explicit-judgment volume yet; the router must remain shadow.
- SearXNG is disabled in the current environment, so X/Threads/Reddit web-index learning remains externally
  unavailable. This does not alter direct/public source operation.
- Configuration rollback covers adaptive configuration; source-code deployment rollback remains an
  operator/version-control responsibility.

MAFER VERIFIED FOR MIRSAD v1.0
