# MIRSAD Live Social Credential Pilot

Generated: 2026-08-09 (Asia/Baghdad)

## Environment

- Application: MIRSAD `1.0.0-rc1`.
- Root `.env`: absent. `Settings` also inspected the process environment through
  the secret-safe verifier; no credential-requiring social connector was configured.
- Ranking remained frozen: top-20 lexical candidate admission, 25% lexical / 75%
  local semantic reranking, and a 1% secondary quality budget.
- Semantic model remained
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, model-version key
  `fastembed-mean-pooling-v1`.
- Holdout hashes remained
  `321f8f149552cdc8e8e0f6e07dca92972c86650d3ad4dc91e611aca5ba5123ee`
  (documents) and
  `c003fca383cf3bd9fb7e0f8bf5ec0eedf748d69fd144b1b803ce5447e2e9db29`
  (judgments). The closed holdout was not rerun.
- Mock data was not used in any live source probe or persisted live pilot session.

The immutable pre-pilot record is in `reports/live-social-pilot-baseline.md`.

## Configured Social Sources

The preferred gate was three live social connectors. Observed gate: **0 / 3**.

| Source | State | Credential validation | Latency | Evidence |
| --- | --- | --- | ---: | --- |
| X | UNCONFIGURED | Not attempted; bearer token absent | 0.03 ms | Safe local configuration check |
| Threads | UNCONFIGURED | Not attempted; access token absent | 0.02 ms | Safe local configuration check |
| Telegram Public Channels | UNCONFIGURED | Not attempted; API ID, API hash, and local user session absent | 0.01 ms | Safe local configuration check |
| Reddit | UNCONFIGURED | Not attempted; approved client credentials absent | 0.01 ms | Safe local configuration check |
| YouTube | UNCONFIGURED | Not attempted; API key absent | 0.01 ms | Safe local configuration check |
| Mastodon | UNCONFIGURED | Not attempted; instance URL and token absent | 0.01 ms | Safe local configuration check |
| Instagram | UNCONFIGURED | Not attempted; professional-account hashtag access absent | 0.01 ms | Safe local configuration check |
| TikTok | APPROVAL_REQUIRED | Research approval and credentials absent | 0.01 ms | No network request |
| Bluesky | NETWORK_BLOCKED | Credential-free public endpoint returned HTTP 403 | 328.90 ms | Minimal live validation request |

No source qualified as `LIVE`. No authentication, scope, refresh, expiry, or quota
claim was made for an unconfigured connector. No token value was printed, returned
by an API, written to either export, or added to a report.

## Credential Validation

`npm run verify-sources` exited zero because no local application failure occurred.
Unconfigured optional sources were warnings, Bluesky was a safe external failure,
and configured supplemental public endpoints were validated separately. The final
run completed at `2026-08-09T01:34:33.996572Z`.

Credential expiry and refresh could not be exercised because no expiring social
credential was present. MIRSAD did not create, guess, or acquire credentials.

## Blocked / Restricted Sources

- Bluesky: public endpoint access was forbidden from this environment (`http_403`).
- TikTok: Research API approval and credentials are required.
- Facebook: unrestricted global public-post keyword search is not available.
- LinkedIn: unrestricted global public-post search is not available.
- Instagram remains capability-limited to approved hashtag/professional-account
  access and was unconfigured; it was not described as global keyword search.
- Mastodon remains configured-instance scoped and was unconfigured.

## Arabic Queries

The required social Arabic matrix was **not executed** because no connector was
eligible to return social records. Repeating rejected/unconfigured calls would not
create evidence. Low-volume supplemental public checks were run and kept separate:

| Query | Mode | Sources | Results | Unique | Duration |
| --- | --- | --- | ---: | ---: | ---: |
| `العراق` | keyword | GitHub, Hacker News | 1 | 1 | 853 ms |
| `اَلْعِرَاق` | exact phrase, observational limitation check | GitHub, Hacker News | 16 | 15 | 1,181 ms |

The remaining Arabic social set (`بغداد`, `الذكاء الاصطناعي`, `وزارة التخطيط`,
`التكنولوجيا`, organization and hashtag variants) remains pending legitimate
social access. It was not redirected to non-social sources to inflate coverage.

## English Queries

No English social query produced an eligible request. Supplemental checks:

| Query | Sources | Results | Unique | Duration | Status |
| --- | --- | ---: | ---: | ---: | --- |
| `artificial intelligence` | Bluesky, HN, GitHub, GDELT, RSS | 50 | 47 | 3,993 ms | Partial: Bluesky 403, GDELT timeout |
| `open data` | Bluesky, HN, GitHub, GDELT, RSS | 50 | 47 | 3,623 ms | Partial: Bluesky 403, GDELT timeout |

Other proposed English social queries were not issued after the social eligibility
check failed.

## Mixed-Language Queries

| Query | Scope | Results | Duration | Observation |
| --- | --- | ---: | ---: | --- |
| `AI العراق` | live verifier across configured sources | 0 social; 0 supplemental matches | connector-specific | Honest empty response |
| `Microsoft العراق` | GitHub and Hacker News supplemental | 0 | 956 ms | Honest empty response |

No mixed-language social relevance judgment was possible.

## Live Connector Counts

The supplemental live verifier used `العراق`, `artificial intelligence`, and
`AI العراق`. Counts are sums over the three probes.

| Connector | State | HTTP/API | Fetched | Schema-valid | Matching | Normalized | Malformed | Attempts | Total latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bluesky | unavailable | HTTP 403 | 0 | 0 | 0 | 0 | 0 | 3 | 831 ms |
| Hacker News | healthy | HTTP 200 | 10 | 10 | 10 | 10 | 0 | 3 | 2,048 ms |
| GitHub | healthy | HTTP 200 | 11 | 11 | 11 | 11 | 0 | 3 | 1,675 ms |
| GDELT | degraded | timeout, then open circuit | 0 | 0 | 0 | 0 | 0 | 4 | 6,004 ms across probes |
| RSS | healthy | HTTP 200 | 90 | 90 | 0 | 0 | 0 | 3 | 1,127 ms |

RSS's 90 fetched records were all schema-valid and all 90 were excluded by query
matching. This is not a normalization failure. GDELT consumed about 3.002 seconds
on each of its first two independently invoked probes; after the failure threshold,
the third probe returned from the open circuit in 0.01 ms.

## Live Latencies

The full `artificial intelligence` mixed supplemental session recorded:

- Bluesky: 332.22 ms, HTTP 403, one attempt.
- RSS: 420.42 ms, HTTP 200, 30 fetched/valid and zero query matches.
- Hacker News: 1,152.66 ms, HTTP 200, 50 fetched/valid/normalized, 40 common-pipeline matches, 10 collected after the global limit.
- GitHub: 1,396.25 ms, HTTP 200, 50 fetched/valid/normalized, 49 common-pipeline matches, 40 collected.
- GDELT: 3,001.05 ms total budget, two attempts (1,560.96 and 1,189.15 ms plus bounded backoff/overhead), timeout.
- Connector collection: 3,020.28 ms; complete API response: 4,015.82 ms wall clock.

No natural rate limit occurred. GitHub correctly disclosed the lower anonymous API
limit. MIRSAD did not intentionally consume quota to force a 429.

## Time to First Useful Result

- Search start: API request start.
- Fastest completion: Bluesky failure at 332 ms; this was not useful data.
- First useful source completion: Hacker News at 1,153 ms.
- GitHub useful completion: 1,396 ms.
- First useful result availability to the current client: about 4,016 ms, because
  the existing REST architecture returns the unified result after all bounded
  connector tasks and local processing finish; it does not stream records.
- Slowest connector: GDELT at its 3,001 ms total budget.
- Local post-collection phases: persistence 35.24 ms, deduplication 50.30 ms,
  ranking 809.67 ms, clustering 51.31 ms.

The search returned `partial` with 50 usable results rather than appearing failed.
No streaming redesign was attempted.

## Semantic Cold / Warm Cost

API diagnostics on real retrieved content:

| Measurement | Cold | Warm repeat |
| --- | ---: | ---: |
| Semantic candidates | 20 | 20 |
| Reranking duration | 787.02 ms | 4.32 ms |
| Document cache hits | 0 | 20 |
| Document cache misses | 20 | 0 |
| Full local ranking phase | 809.67 ms | 25.96 ms |

An isolated measurement using those same 20 real documents separated the cold
work: model initialization 691.59 ms, query embedding 6.85 ms, document embedding
130.54 ms, and cosine calculation 1.70 ms (830.68 ms measured total). Peak process
RSS increased by 680,692 KiB during this isolated cold load. This is a bounded
observation, not a formal memory-leak claim.

The API exposed model and version, and an immediate repeat produced 20/20 cache
hits. A model-unavailable regression test proved lexical fallback returns valid
results, reports `semantic_state=unavailable`, and does not return HTTP 500. The
normal semantic configuration was restored and remained `semantic_ranking:ready`.

## Real Result Traces

No real social result existed to trace. Two supplemental records proved the shared
pipeline without being counted as social:

1. GitHub repository external ID `1328112175`, URL
   `https://github.com/Ibrar-16/Artificial-Intelligence`: HTTP 200 connector record,
   normalized `source_type=repository`, persisted with Arabic-safe UTF-8 fields,
   admitted to FTS, scored with lexical relevance 99.97 and semantic relevance
   87.84, assigned a cluster, returned by API/UI, and present in JSON/CSV export.
2. Hacker News record external ID `49223413`, canonical source URL
   `https://waitbutwhy.com/2015/01/artificial-intelligence-revolution-1.html`:
   HTTP 200 connector record, raw points/comments preserved, normalized engagement
   14.35, lexical relevance 100.00, semantic relevance 86.96, persisted and exported.

Database evidence after the bounded sessions: 116 content rows, 116 FTS rows, 167
session-result rows, 138 cluster rows, and 8 duplicate groups. `PRAGMA
integrity_check` returned `ok`; `foreign_key_check` returned no rows.

## Manual Relevance Observation

Social Precision@5, Precision@10, and first-relevant rank are **NOT MEASURED**:
there were zero eligible social records. The rationale and supplemental observations
are in `reports/live-relevance-observation.md`. No score was reported as a social
relevance metric and no pilot example was used to tune ranking.

## Platform Distribution

The `artificial intelligence` supplemental session contained GitHub 40 and Hacker
News 10. It contained zero Social and zero News records; social reach and social
platform diversity correctly remained null/zero rather than fabricated.

## Platform Bias Review

GitHub supplied 80% of the collected supplemental set, largely because the global
50-record cap admitted 40 GitHub candidates after relevance ordering. This did not
translate into universally higher scores: GitHub mean score was 52.04 versus 72.60
for Hacker News, with means of 72.60 versus 92.70 for lexical relevance. The sample
does not support a social-platform bias conclusion because it contains no social
records. No diversity quota or ranking change was applied.

## Duplicate / Repost Behavior

The supplemental session detected three duplicate copies and reported 47 unique
records from 50 collected. Duplicate originals remained accessible. No genuine
social repost, quote/repost, Telegram forward, or cross-platform copied
announcement could be verified without social data.

## Story Clustering

The session produced 39 clusters. Inspection found two apparent cross-source
clusters that grouped unrelated GitHub and Hacker News items primarily because all
shared the broad phrase `artificial intelligence`. This is a concrete clustering
precision risk: duplicate grouping remained correct, but broad-topic clusters can
overstate story coherence. It was documented rather than tuned against one live
query during this frozen-ranking pilot.

## Cross-Source Presence

No valid real social cross-platform story was available. The two multi-source
supplemental clusters were not accepted as proof because manual inspection showed
they were broad-topic false groupings. MIRSAD did label their earliest timestamp as
`First Seen by MIRSAD`, not true origin.

## Arabic RTL Verification

Opt-in Playwright loaded the real Arabic supplemental session
`2d6eee95-1e3c-48ee-867a-0e6b81d53aa4`, verified retrieved Arabic text was visible
with `dir="auto"`, verified a safe external source link, switched EN -> AR -> EN,
kept the same route and result, and issued zero replacement search requests.

## English LTR Verification

Opt-in Playwright loaded the real supplemental session
`78f0ee07-1284-4556-8302-e105b3063877`, opened score explanation and diagnostics,
verified export and external links, switched EN -> AR -> EN, retained the session,
and issued no replacement search request. Browser console/page-error monitoring
reported no error in either live test.

## Exports

- JSON: HTTP 200, 70,859 bytes, schema `mirsad.search-export`, version `1.0`, 50 records.
- CSV: HTTP 200, 23,553 bytes, 51 physical rows including header, UTF-8 BOM
  `EF BB BF`, 50 records.
- Arabic, URLs, nullable metrics, source type, score components, cluster IDs, and
  duplicate IDs use the authoritative stored response. All 50 unavailable
  `like_count` fields remained null in JSON rather than becoming zero.
- No credential names/values were present in JSON paths. CSV formula-prefix
  protection remains covered by deterministic export tests; this live sample did
  not contain a formula-prefixed external field.

## Rate Limits

No connector naturally returned HTTP 429. GitHub disclosed anonymous lower-rate
limits. GDELT used bounded timeout/backoff and opened its circuit after repeated
timeouts. No aggressive retry or deliberate quota exhaustion was performed.

## Known Limitations

- No legitimate social credential was available, and Bluesky was externally
  forbidden, so real social normalization, engagement, reposts, clusters, social
  analytics, social export fields, and observational relevance remain unproven.
- The REST search response is non-streaming; useful connector completion is
  instrumented, but the client receives results after bounded collection completes.
- Cold MiniLM loading increased process RSS by about 665 MiB in the isolated
  measurement; warm reranking was fast.
- Broad common-topic text can produce overly broad story clusters, observed in
  the supplemental sample. No pilot-specific clustering tuning was applied.
- GitHub anonymous access has a lower rate limit; GDELT was unavailable within its
  interactive budget in this environment.

## External Blockers

The social gate requires operator-supplied, legitimate credentials/approval for at
least three sources, or restored legitimate access to a credential-free source.
Current blockers are absent credentials for X, Threads, Telegram, Reddit, YouTube,
Mastodon, and Instagram; TikTok Research approval; and environmental HTTP 403 for
Bluesky.

## Internal Defects Discovered

- **Fixed:** a stale database row for the deterministic mock connector appeared in
  `/api/v1/sources` despite the connector being disabled and absent from the active
  registry. Source management now filters retained provenance rows by the runtime
  connector registry. A regression test proves stale unregistered sources are not
  exposed; the live API now returns 15 production connectors and no mock.
- **Observed, not tuned:** story clustering can merge unrelated records sharing a
  broad exact topic phrase. This affects cluster interpretation but did not corrupt
  retrieval, persistence, ranking, duplicate grouping, or export in the pilot.

## Validation

- Backend: 103 tests passed.
- Frontend: 13 tests passed.
- Playwright deterministic: 11 passed, 2 opt-in live tests skipped by default.
- Playwright real persisted sessions: 2 passed (English and Arabic).
- Lint: backend Ruff and frontend Oxlint passed.
- TypeScript: passed.
- Production Vite build: passed (2,769 modules transformed).
- Doctor: passed all mandatory checks; warned only that `.env` is absent.
- Source verifier: exited zero; optional unconfigured/restricted sources did not
  constitute a local application failure.
- Database: integrity `ok`, zero foreign-key violations, FTS rows equal content rows
  (116/116).
- Startup: API and frontend both reached localhost readiness. The development
  session completed all local API/browser evidence without unexpected backend
  exceptions.

## Decision

MIRSAD’s internal mixed-source pipeline, semantic cache/fallback, partial-failure
handling, UI direction/state, and exports operated correctly on real supplemental
public records. The required social evidence does not exist in this environment:
zero social connectors returned records, so the three-source gate and real social
quality assessment are blocked by legitimate credentials/approval/access.

SOCIAL PILOT PARTIAL
