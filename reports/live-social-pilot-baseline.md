# Live Social Pilot Baseline

Recorded: 2026-08-09 (Asia/Baghdad)

This baseline was captured before the live social credential pilot. No connector
configuration, ranking code, holdout corpus, or holdout judgment was changed.

## Application

- Version: `1.0.0-rc1`
- Environment file: root `.env` absent; configuration therefore comes from process
  environment and code defaults.
- Mock connector default: disabled.

## Frozen Ranking

- Candidate retrieval: intent-aware lexical candidates using SQLite FTS5 BM25.
- Candidate limit: 20.
- Semantic model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Semantic model version: `fastembed-mean-pooling-v1`.
- Lexical weight: 25%.
- Semantic weight: 75%.
- Secondary quality budget: 1%.
- Duplicate presentation: representatives precede duplicate copies.

## Frozen Holdout Integrity

- Documents SHA-256: `321f8f149552cdc8e8e0f6e07dca92972c86650d3ad4dc91e611aca5ba5123ee`.
- Judgments SHA-256: `c003fca383cf3bd9fb7e0f8bf5ec0eedf748d69fd144b1b803ce5447e2e9db29`.
- The two current files match these recorded hashes.
- The holdout is closed and will not be rerun or used for pilot tuning.

## Frozen Holdout Result

| Slice | P@5 | P@10 | MRR |
| --- | ---: | ---: | ---: |
| Overall | 0.3625 | 0.2938 | 0.6652 |
| Arabic | 0.1600 | 0.2600 | 0.3952 |
| English | 0.4750 | 0.2875 | 0.8333 |
| Mixed | 0.4000 | 0.3667 | 0.6667 |

Overall Recall@10 was 0.8698, Recall@20 was 1.0000, nDCG@5 was 0.4948,
and nDCG@10 was 0.6528.

## Verified Test Baseline

The immediately preceding relevance-recovery verification recorded 102 backend
tests passed, 13 frontend tests passed, 11 deterministic Playwright tests passed,
and one opt-in credentialed live Playwright test skipped. This pilot will run
targeted operational regression checks after live verification; these counts are
baseline evidence, not substitutes for the fresh pilot commands.

## Pre-Pilot Connector State

The last recorded secret-safe verification showed Bluesky configured through its
public endpoint but rejected with HTTP 403 in this environment. X, Threads,
Telegram, Reddit, YouTube, Mastodon, and Instagram were unconfigured; TikTok,
Facebook, and LinkedIn were restricted. GitHub and Hacker News public endpoints
were reachable; RSS and GDELT required no credentials. A fresh `verify-sources`
run is the authoritative state for this pilot.
