# Live Relevance Observation

Generated: 2026-08-09

## Scope

This report is an observational pilot evaluation, not a blinded benchmark and not
an extension of the frozen relevance holdout. The frozen corpus and judgments
were not rerun, edited, or used for tuning.

## Eligibility Result

No social connector returned a real record in this environment. X, Threads,
Telegram, Reddit, YouTube, Mastodon, and Instagram were unconfigured; TikTok
required approved Research API access; Bluesky returned HTTP 403 from its public
endpoint. Therefore there was no eligible social top-10 cohort to judge.

| Metric | Result |
| --- | --- |
| Social Precision@5 | NOT MEASURED |
| Social Precision@10 | NOT MEASURED |
| Social first relevant rank | NOT MEASURED |
| Social source/platform breakdown | 0 live sources / 0 records |

GitHub, Hacker News, RSS, and GDELT were not substituted for social sources.
Reporting a precision value over those supplemental sources as a social pilot
metric would be misleading.

## Supplemental Observations

These observations validate operation only and are excluded from the social
relevance metric:

- `artificial intelligence` produced 50 persisted GitHub/Hacker News results. The
  first ten visibly matched the query phrase, but no blinded judgment was made
  and no Precision@K is claimed.
- `العراق` produced one real GitHub record whose Arabic description contained the
  query. It passed normalization, local semantic reranking, persistence, UI
  rendering, and `dir="auto"` validation.
- `Microsoft العراق` returned zero records. MIRSAD preserved this as a valid empty
  result rather than fabricating coverage.
- Exact phrase `اَلْعِرَاق` normalized to `العراق` and produced 16 records, 15
  unique, from the 30-day GitHub/Hacker News supplemental window. This is an
  observation of the known diacritized Arabic path only; no ranking or
  normalization constant was changed.

## Ranking Failures Observed

No social ranking failure could be assessed without social records. In the
supplemental `artificial intelligence` session, deterministic clustering grouped
unrelated broad-topic GitHub and Hacker News records because they shared the full
query phrase. This is a clustering-quality observation, not a ranking-tuning
input, and is recorded in the pilot report.

## Next Measurement

Once at least one legitimate social connector returns records, an evaluator can
capture score-hidden top-10 lists for the predefined Arabic, English, and mixed
query sets and assign `RELEVANT`, `PARTIALLY_RELEVANT`, or `IRRELEVANT` judgments.
Until then, live social Precision@5 and Precision@10 remain unmeasured.
