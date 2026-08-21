# MIRSAD Evidence-Gap Closure

Generated 2026-08-09 for MIRSAD `v1.0.0-rc1`. This pass changed no product scope or
architecture. It added independent evaluation evidence, localized application-owned connector
prose, and regression instrumentation for existing reliability requirements.

## Non-PASS Requirements

| ID | Prior | Final | Basis |
| --- | --- | --- | --- |
| R01 revision/dirty state | NOT_PROVEN | NOT_PROVEN | `.git/` is empty. This is a source snapshot; no history was invented. |
| R26 component distributions | PARTIAL | PASS | Variable holdout distributions now cover every score component. |
| R28 evaluation independence | PARTIAL | PASS | A separate 110-document/16-query holdout has at least 12 candidates/query and independent judgment storage. |
| R45 portal direction matrix | PARTIAL | PASS | Every production-used portal primitive passes EN -> AR -> EN direction, keyboard, focus, and alignment checks. |
| R48 localization completeness | PARTIAL | PASS | Connector coverage, configuration, warning, and failure prose now uses source/error translation keys. |
| R61 memory/resource sanity | PARTIAL | PARTIAL | Repeated backend and browser observations are bounded; formal leak freedom is not claimed. |
| R81 three live social connectors | BLOCKED_EXTERNAL | BLOCKED_EXTERNAL | Credentials remain absent and Bluesky remains HTTP 403. No mock is counted as live evidence. |

Detailed root causes and closure criteria are in `reports/open-verification-items.md`.

## Blinded Relevance Holdout

The current ranking implementation was executed unchanged against a frozen corpus and a separate
judgment file. The evaluator uses fixed-K precision, treats unjudged results as irrelevant, does not
double-count a judged near duplicate, and reports substantial candidate pools.

| Segment | Queries | P@5 | P@10 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Arabic | 5 | 0.0000 | 0.3000 | 0.1286 |
| English | 8 | 0.0000 | 0.2000 | 0.1181 |
| Mixed Arabic/English | 3 | 0.1333 | 0.3333 | 0.4286 |
| Exact phrase | 6 | 0.0000 | 0.2500 | 0.1234 |
| Ambiguous | 2 | 0.0000 | 0.2500 | 0.1340 |
| Hard | 10 | 0.0400 | 0.2600 | 0.2133 |
| Overall | 16 | 0.0250 | 0.2562 | 0.1796 |

The values are intentionally not optimized. The holdout concentrates difficult candidates that all
contain the same exact query name or phrase; median lexical relevance is 100. Semantic name
collisions therefore saturate deterministic lexical relevance and are ordered by recency and public
engagement. This is a measured limitation, not a metric implementation error. No ranking constants
were changed after the baseline.

The previous primary P@5/P@10/MRR relationship is mathematically correct. Its 20 queries average
1.25 relevant and 1.25 returned documents, all with the first relevant item at rank one. One relevant
item at rank one contributes P@5 `0.20`, P@10 `0.10`, and MRR `1.00`. The hard set averages 1.40
relevant and 1.87 returned documents; 13/15 first relevant items are rank one, yielding P@5 `0.2800`,
P@10 `0.1400`, and MRR `0.9222`.

## GDELT Wall Clock

The connector already wraps the complete retry loop in one strict total budget. Monotonic
deterministic evidence measured:

| Measurement | Search 1 | Search 2 |
| --- | ---: | ---: |
| Attempt 1 | 20.14 ms | 20.13 ms |
| Retry backoff | 250.49 ms | 250.52 ms |
| Attempt 2 | 20.14 ms | 20.11 ms |
| Total connector wall clock | 291.15 ms | 291.06 ms |
| Configured total budget | 350 ms | 350 ms |
| Circuit after call | closed | open |

The next open-circuit response took `0.007 ms` with zero HTTP attempts. In the live configuration,
one search stopped at `3,001.62 ms`; a separate second search stopped at `3,002.17 ms` and opened the
breaker. The prior approximately six-second aggregate was two calls, not one retry loop.

## First Useful Result

A deterministic mixed search recorded fast, medium, and failing connectors completing at `32.52`,
`92.70`, and `182.92 ms`. The current non-streaming REST API exposed the partial result at `197.85
ms` with two healthy records and a warning for the failed source. MIRSAD does not expose incremental
results before the response completes; the slow source remains bounded and does not discard healthy
results.

## Localization And Portals

`source-presentation.ts` now maps current connector coverage/configuration prose by source key and
failure prose by machine-readable category. Arabic never falls back to an unknown backend English
sentence; canonical platform names, HTTP identifiers, and external post content remain unchanged.

The complete portal set imported by production is Dialog, Sheet, Dropdown Menu, Select, and Tooltip.
Each passed EN -> AR -> EN computed direction, viewport alignment, keyboard opening/navigation,
focus containment/return, and Escape closing. Command and Popover wrappers are not imported by a
production feature and were not tested merely to inflate coverage.

## Resource Observation

Backend VmRSS snapshots after 1, 10, 20, and 30 repeated searches plus a 200-result workflow ranged
over `4,256 KiB`. Browser CDP snapshots surrounding 20 locale switches, eight Sheet/Dialog cycles,
and route navigation changed post-GC heap from `24,179,612` to `23,037,608` bytes and nodes from
`3,708` to `1,483`. No monotonic unbounded growth was observed. This remains bounded observational
evidence, not formal retained-heap analysis.

## Live Source Sanity

| Source/workflow | Fetched | Valid | Matching | Normalized | Collected/persisted | Latency | State |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Hacker News, mixed `open data` session | 25 | 25 | 25 | 25 | 6 | 1,364.17 ms | healthy |
| GitHub, mixed `open data` session | 25 | 25 | 25 | 25 | 19 | 1,004.06 ms | healthy, anonymous |
| RSS positive `Hormuz` session | 30 | 30 | 1 | 1 | 1 | 372.70 ms | healthy |
| RSS absent-token proof | 30 | 30 | 0 | 0 | 0 | captured-response parser proof | healthy/empty |
| GDELT, first live probe | 0 | 0 | 0 | 0 | 0 | 3,001.62 ms | degraded timeout |
| Bluesky, `open data` | 0 | 0 | 0 | 0 | 0 | 294.87 ms | unavailable HTTP 403 |

The mixed Hacker News/GitHub/RSS/Bluesky session completed in `1,458 ms`, collected 25 records,
reported 23 unique records and 20 clusters, preserved safe original links, and exported 52,303-byte
JSON plus 14,599-byte UTF-8-BOM CSV. GDELT was verified separately because its connector instance
circuit state is intentionally persistent during repeated probes.

## Final Validation

| Gate | Fresh result |
| --- | --- |
| Backend | 87 passed in 3.63 s; 0 skipped/xfail |
| Frontend | 12 passed across 5 files in 5.00 s |
| Playwright | 11 passed; 1 explicit live-only skip; no console errors |
| Localization stress | 20 Search switches plus 20 switches across Search/Results/Analytics/Settings passed |
| Portal matrix | 5/5 production-used primitives passed |
| Original/hard relevance | Primary 0.2500/0.1250/1.0000; hard 0.2800/0.1400/0.9222 P@5/P@10/MRR |
| Blinded holdout | 16/16 queries evaluated with 12+ candidates |
| GDELT timing | Total-budget, breaker, and open-circuit tests passed |
| RSS | Positive/negative stage tests and live positive persistence passed |
| Lint/typecheck | Ruff, oxlint, and TypeScript passed |
| Production build | 2,769 modules transformed |
| Doctor | All required checks PASS; absent optional `.env` is WARN |
| verify-sources | Exit 0; optional absence WARN; Bluesky classified FAIL/HTTP 403 |
| Database | Reset passed; integrity `ok`; 0 FK violations; content=FTS=0 |
| FTS lifecycle | Insert/update/delete/rebuild tests passed |
| Startup | API/frontend readiness passed; duplicate start rejected; stop succeeded |

## Final Matrix

| Status | Count |
| --- | ---: |
| PASS | 85 |
| PARTIAL | 1 |
| FAIL | 0 |
| NOT_APPLICABLE | 0 |
| NOT_PROVEN | 1 |
| BLOCKED_EXTERNAL | 1 |

The sole PARTIAL is the deliberately bounded scope of memory evidence. Git traceability remains
NOT_PROVEN because the directory is a source snapshot; initialize a real local repository before
formal handoff rather than fabricating upstream history. The social blocker remains external.

INTERNAL VERIFICATION COMPLETE — READY FOR LIVE SOCIAL CREDENTIAL PILOT
