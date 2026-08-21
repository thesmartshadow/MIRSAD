# Open Verification Items

Captured 2026-08-09 from the 88-row matrix in
`reports/final-independent-verification.md` before the evidence-gap closure changes.

| ID | Exact requirement | Prior status | Why it was not PASS | Limitation type | Safe local resolution |
| --- | --- | --- | --- | --- | --- |
| R01 | Revision and dirty state known | NOT_PROVEN | `.git/` is an empty directory. Git cannot identify a revision, history, tracked files, ignored files, or a clean/dirty state. | Environment / evidence quality | No, not without inventing a new history boundary. The directory behaves as a source snapshot. Initialize Git before formal handoff, but do not create history during verification without an explicit repository workflow decision. |
| R26 | Component distributions | PARTIAL | The existing hard fixture holds Source Confidence at 70, Cross-Source Presence at 0, and Novelty at 100, so those components have zero variance and cannot be calibrated from that fixture. | Evidence quality / test data | Yes. A separate holdout can vary source confidence and duplicate/cross-source context without changing production ranking constants. |
| R28 | Evaluation independence | PARTIAL | The primary set has only 1-2 candidates per query and the hard fixture was visible during earlier ranking work. It is useful regression evidence but not a blinded holdout with substantial negatives. | Evidence quality / test coverage | Yes. Add a separately stored holdout corpus and judgments that are not imported by ranking production code and were not used to choose current constants. Measure the unchanged algorithm first. |
| R45 | Portal direction matrix | PARTIAL | Dialog, Sheet, Dropdown Menu, Select, and Tooltip are used in production, but their complete EN -> AR -> EN direction, focus, keyboard, and alignment behavior was not exercised as one explicit matrix. Command and Popover wrappers exist but are not imported by production features. | Test coverage | Yes for every production-used portal primitive. Do not test unused Command/Popover wrappers merely to inflate coverage. |
| R48 | Localization completeness | PARTIAL | Connector `coverage_label`, health `detail`/`recent_failure`, and search `warning.message` values are backend-owned English prose rendered directly in Arabic pages. Platform names and technical identifiers are correctly canonical, but application-owned explanations are not localized. | Code / test coverage | Yes. Keep machine-readable source/status/capability metadata authoritative and map application-owned explanation codes/source keys through the shared localization layer, with safe fallback for unknown future connectors. |
| R61 | Memory/resource sanity | PARTIAL | One benchmark peak-RSS sample proved bounded execution but not behavior across repeated searches, navigation, locale changes, and overlay cycles. It was correctly not called a formal memory-leak proof. | Evidence quality / specialized tooling | Partly. Run bounded repeatable API and browser stress observations with before/after process snapshots. Preserve PARTIAL unless specialized heap-retention tooling establishes formal leak freedom. |
| R81 | Three live social connectors | BLOCKED_EXTERNAL | No legitimate X, Threads, Telegram, Reddit, YouTube, Mastodon, Instagram, or TikTok credentials are configured, and Bluesky returns HTTP 403 from this environment. | External access / environment | No. Keep deterministic adapter verification, but only the operator/platform can supply approved credentials or restore network access. Never replace the blocker with fixtures. |

## Closure Policy

- R26 and R28 can become PASS only if a separately judged holdout contains substantial irrelevant
  candidates, meaningful P@5/P@10 denominators, language slices, and variable score components.
- R45 can become PASS only for portal primitives actually imported by production code.
- R48 can become PASS only when Arabic no longer exposes application-owned English connector prose.
- R61 remains PARTIAL if the result is observational rather than a formal retained-heap proof.
- R01 remains NOT_PROVEN unless real Git history is supplied or a deliberate handoff repository is
  initialized outside this verification pass.
- R81 remains BLOCKED_EXTERNAL until at least three legitimate social sources return live records.

## Closure Results

| ID | Final status | Evidence added | Resolution |
| --- | --- | --- | --- |
| R01 | NOT_PROVEN | Rechecked `.git/`; it remains an empty directory and every Git history/status command fails. | This is accurately treated as a source snapshot. No fabricated repository or commit was created. Initialize Git deliberately before formal handoff. |
| R26 | PASS | `npm run evaluate:holdout`; `test_blinded_holdout_exercises_nonconstant_score_components` | The holdout varies Source Confidence (stddev 16.57), Cross-Source Presence (19.30), and Novelty (24.27), with complete distribution statistics. |
| R28 | PASS | Separate 110-document corpus and 16-query judgment file; minimum 12 candidates/query; three holdout tests | The unchanged current ranker was measured before any tuning. Low results are retained honestly in `blinded-relevance-holdout.md`. |
| R45 | PASS | Playwright `all production portal primitives preserve direction, focus, and keyboard behavior` | Dialog, Sheet, Dropdown Menu, Select, and Tooltip are the complete production-imported portal set and pass EN -> AR -> EN. Command and Popover wrappers are not used by production code. |
| R48 | PASS | `source-presentation.ts`, two unit regressions, Arabic Search/Sources portal test | Application-owned coverage/configuration/failure prose is localized by source key and error category. Platform brands and technical identifiers remain canonical. |
| R61 | PARTIAL | 31 backend searches including a 200-result run; browser CDP snapshots after 20 switches, overlays, and navigation | Backend VmRSS varied 4,256 KiB; browser post-GC heap decreased. This is bounded observation and intentionally not called formal leak freedom. |
| R81 | BLOCKED_EXTERNAL | Fresh `verify-sources`, `verify:live`, and mixed live API/export session | No credentialed social source returned records; Bluesky remains HTTP 403. The blocker is unchanged and no fixture is presented as live success. |

Final matrix counts: **85 PASS, 1 PARTIAL, 0 FAIL, 1 NOT_PROVEN, 1 BLOCKED_EXTERNAL**.
