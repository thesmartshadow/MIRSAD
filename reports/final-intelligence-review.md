# Final Intelligence Review

## Executive Assessment

MIRSAD's deterministic search pipeline is operational and more predictable under malformed input,
concurrent completion, weak lexical matches, duplicate chains, missing metrics, old analytics data,
and partial source failure. Live Hacker News and GitHub content completed the full API/UI/export path.
The application is engineering-ready, but the social pilot gate is pending credentials and reachable
social APIs.

## Bugs Discovered

The review found ambiguous RSS stage accounting, unbounded aggregate GDELT latency, cross-task
diagnostic mutation, unstable tie ordering, transitive false duplicate merges, unsafe malformed-port
canonicalization, absent-metric coercion, truncated analytics windows, incorrect empty-partial status,
stale search response ownership, direction flash/sidebar placement errors, and false-positive startup.
The evidence and per-finding validation are in `reports/deep-audit.md`.

## Root Causes

The recurring causes were conflated pipeline stages, reuse of generic network policy for a uniquely
slow source, process-global mutable telemetry, unstable internal identifiers, identity clustering by
single-link transitivity, physical rather than logical layout, and operational checks that tested
process existence rather than service readiness.

## Algorithmic Weaknesses Found

The legacy candidate/ranking boundary admitted substring-like collisions, did not explicitly encode
phrase/title proximity, and used a supporting-signal gate that was nearly saturated for weak matches.
Near-duplicate similarity could also become transitive even though duplicate identity is not.

## Algorithmic Improvements Implemented

Candidate generation is now separate and intent-aware; relevance combines bounded coverage,
title, phrase, proximity, BM25, hashtag/handle/URL intent; and all supporting score signals use a
squared relevance gate. FTS ranking is restricted to session candidates. Near-duplicate groups use
complete-link admission. Stable external identity is the final ranking tie-breaker.

## Search Quality Before / After

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Primary returned-set P@5 | 0.8850 | 1.0000 | +0.1150 |
| Primary returned-set P@10 | 0.8850 | 1.0000 | +0.1150 |
| Primary MRR | 1.0000 | 1.0000 | 0.0000 |
| Hard returned-set P@5 | 0.6711 | 0.8333 | +0.1622 |
| Hard returned-set P@10 | 0.6667 | 0.8333 | +0.1666 |
| Hard MRR | 0.8022 | 0.9222 | +0.1200 |

Standard fixed-denominator P@5/P@10 are 0.2500/0.1250 on the primary set and 0.2800/0.1400 on the
hard set. The small candidate pools make returned-set precision useful for regression diagnosis but
not a substitute for standard Precision@K. Primary pools average 1.25 candidates, so the perfect
returned-set score has limited external validity.

## Arabic Search Quality

Arabic returned-set P@5/P@10/MRR are 1.0000/1.0000/1.0000 on the primary judged set. Tests cover
diacritics, tatweel, Alef forms, punctuation, Arabic/Persian digits, zero-width controls, hashtags,
proper nouns, mixed language, intended variants, and non-merges. Normalization remains conservative;
the definite-article variant is recorded with its reason rather than silently replacing the query.
The later dense holdout reports Arabic P@5/P@10/MRR `0.0000/0.3000/0.1286`; it deliberately contains
12+ same-phrase semantic collisions per query and was not used to tune constants.

## English Search Quality

English returned-set P@5/P@10/MRR are 1.0000/1.0000/1.0000 on the primary set. The hard set retains
ambiguous lexical collisions such as “climate” in unrelated popular titles; this is documented rather
than hidden by overfitted filtering.
The later dense holdout reports English `0.0000/0.2000/0.1181` and mixed-language
`0.1333/0.3333/0.4286` P@5/P@10/MRR. These values expose relevance saturation on identical phrases.

## Deduplication Assessment

Judged duplicate pair precision and recall are both 1.0000. URL tracking/canonical variants,
fingerprints, Arabic punctuation, small edits, and false transitive chains are covered. Duplicate and
same-story cluster semantics remain separate, and originals are preserved.

## Clustering Assessment

Judged cluster pair precision and recall are both 1.0000 on the deterministic fixture. Input order is
stable. Clustering remains lexical and may fragment bilingual descriptions or miss semantic event
relationships; no unmeasured embedding dependency was added.

## Ranking Calibration

The original hard fixture keeps Source Confidence/Cross-Source/Novelty constant. The independent
holdout closes that calibration gap: their standard deviations are `16.57`, `19.30`, and `24.27`.
Holdout Relevance has median 100/stddev 5.79, which explains why identical exact-phrase semantic
collisions are then ordered by supporting signals. Weak lexical collisions remain relevance-gated;
the holdout exposes the separate boundary where lexical evidence itself is indistinguishable.

## Performance Scaling

Normalization/ranking at 100, 1,000, 5,000, and 10,000 records measured 0.32/3.74 ms,
3.26/34.63 ms, 17.14/169.00 ms, and 33.83/348.66 ms. Deduplication measured 93.43 ms at 100 and
378.33 ms at the production cap of 200. The representative concurrent fixture search median is
78.26 ms (P95 81.98 ms). Repeated backend RSS observations varied by 4,256 KiB, while post-GC browser
heap decreased during locale/overlay/navigation stress; neither is presented as a formal leak proof.
These are local engine timings, not network timings.

## Arabic/English UI Switching Root Cause

Persisted locale was applied after initial render, while sidebar position, margins, and some overlay
controls used physical LTR assumptions. This created a direction flash and inconsistent component
placement even though translations changed.

## RTL/LTR Fix

The persisted locale initializes `html lang/dir` before React. The i18n provider is the single
authoritative state and updates the document synchronously. Sidebar side, logical spacing, overlay
controls, arrows, and labels follow that provider; retrieved content uses `dir="auto"`.

## State Preservation Verification

Playwright switches EN-AR-EN-AR-EN and performs 20 consecutive switches while preserving the query,
sort/filter form state, sidebar collapse state, route, theme, and open UI ownership. Desktop and narrow
viewport runs report no console errors, duplicate portals, or serious automated accessibility findings.
Dialog, Sheet, Dropdown Menu, Select, and Tooltip additionally pass an explicit EN-AR-EN direction,
alignment, keyboard, focus-entry, focus-return, and close matrix. Connector-owned explanatory prose
is translated by source/error keys rather than rendering backend English in Arabic.

## Connector Reliability

GDELT now has a strict 3-second total interactive budget and circuit breaker. RSS exposes all
pipeline-stage counts. Diagnostics are context-local. GitHub retains successful scopes during partial
scope failure. Failure categories distinguish timeout, network, 401, 403, 404, 429, 5xx, invalid
payload, missing configuration, limited access, and quota.

## Remaining Risks

- No social connector returned live records in this environment; credentials were absent and
  Bluesky returned HTTP 403.
- GDELT remained slow/unreachable during the live run, though it can no longer exceed its budget.
- Ambiguous broad terms remain difficult without semantic context.
- The REST search response is bounded but not streamed, so the UI receives usable records after the
  bounded connector set completes.

## Validation Evidence

The final independent gate supersedes these historical counts; see
`reports/final-independent-verification.md` for the freshly executed backend, frontend, and
Playwright totals.
Ruff, frontend lint, TypeScript, production build, doctor, Docker Compose config, database reset,
SQLite integrity/foreign-key/FTS checks, strict-port startup readiness, search evaluation, source
verification, and benchmarks passed.
