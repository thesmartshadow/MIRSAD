# MIRSAD v1.0.0-rc1 Release Readiness

## Release State

`Engineering Ready / Social Pilot Pending Credentials`

Mandatory code and engineering functional gates pass. The local release-candidate metadata is
`1.0.0-rc1`. The separate Social Pilot Ready gate does not pass because fewer than three real social
connectors were successfully verified live.

## Live Social Sources

No social source returned a live record in this environment. This is not presented as support
failure for unconfigured optional adapters:

| Source | State | Records | Latency | Limitation |
| --- | --- | ---: | ---: | --- |
| X | unconfigured | 0 | 0 ms | Bearer token absent |
| Threads | unconfigured | 0 | 0 ms | Access token absent |
| Telegram | unconfigured | 0 | 0 ms | Public-channel user session absent |
| Reddit | unconfigured | 0 | 0 ms | Approved OAuth credentials absent |
| YouTube | unconfigured | 0 | 0 ms | API key absent |
| Bluesky | unavailable | 0 | 890 ms across 3 probes | HTTP 403 from this environment |
| Mastodon | unconfigured | 0 | 0 ms | Instance URL/user token absent |
| Instagram | unconfigured | 0 | 0 ms | Approved hashtag access absent |
| TikTok | restricted | 0 | 0 ms | Research approval and credentials required |
| Facebook | restricted | 0 | 0 ms | No configured global public-post capability |
| LinkedIn | restricted | 0 | 0 ms | No global public-post API capability |

Implementation-capable but credential-dependent adapters are X, Threads, Telegram Public Channels,
Reddit, YouTube, configured-instance Mastodon, Instagram hashtag media, and approved TikTok Research.
None is counted as live operational without a successful real response.

## Live Supplemental Sources

- Hacker News: healthy; 20 normalized records across three probes; 2,790 ms total. In the `open data`
  end-to-end session, 20 candidates became 8 final matches in 1,075 ms.
- GitHub: healthy through anonymous API access; 17 normalized records across three probes; 1,803 ms
  total. In the same session, 20 candidates became 3 final matches in 333 ms.
- RSS: healthy feed transport/parsing; 90 fetched/schema-valid records and 0 query matches across the
  verification queries; 1,210 ms total.

## Restricted Sources

Facebook and LinkedIn intentionally expose no global public-post keyword search. Instagram is
hashtag/professional-account scoped, not global keyword search. TikTok requires Research API approval.
Mastodon search is configured-instance dependent, not global Fediverse coverage. X full-history
search is conditional on the configured access tier.

## Known Network Limitations

Bluesky AppView returned HTTP 403 and was marked unavailable without circumvention. GDELT did not
respond within the interactive budget. Optional credentialed platforms could not be live-tested
because `.env` is absent. Platform quotas, approval, and geographic/CDN routing remain external.

## RSS Investigation

The prior `78 raw / 0 normalized` observation was an accounting ambiguity, not 78 malformed records.
Current reproduction fetched 90 entries over three probes: all 90 were schema-valid, none malformed,
and none matched the exact query terms. The UI/API now report fetched, schema-valid, query-matching,
time-eligible, excluded, malformed, normalized, and final counts separately. RSS HTML stripping,
provenance, timestamps, URLs, lexical behavior, and partial feed failure have regression coverage.

## GDELT Investigation

The previous roughly 18.9-second aggregate came from repeated bounded attempts without a connector
wall-clock budget. GDELT now permits at most a three-second interactive total, with 1.25-second
attempt deadlines, one retry/backoff, and a breaker after two timeout searches. Live evidence was
3,001 ms/two attempts, 3,002 ms/two attempts, then immediate `circuit_open`; healthy sources remained
available.

## Search Quality

Primary standard P@5/P@10 are 0.2500/0.1250; returned-set P@5/P@10 and MRR are
1.0000/1.0000/1.0000. The separate adversarial set has standard P@5/P@10 of 0.2800/0.1400;
returned-set P@5 improved from 0.6711 to 0.8333 and MRR from 0.8022 to 0.9222. Arabic, English,
and mixed standard primary P@5 are 0.2286, 0.2667, and 0.2000 respectively. The small primary
candidate pools limit external validity. Judged duplicate and cluster pair precision/recall are
1.0000/1.0000.

The independent holdout has 110 documents, 16 queries, and at least 12 candidates per query. With
the current ranking unchanged it reports overall P@5 `0.0250`, P@10 `0.2562`, and MRR `0.1796`;
Arabic/English/mixed P@5 are `0.0000`/`0.0000`/`0.1333`. The intentionally dense same-phrase
collisions expose lexical relevance saturation rather than a metric error. No constants were tuned
against this holdout.

## Real Performance

Internal engine and live network numbers are separate. The deterministic three-connector fixture
median/P95 is 76.18/78.53 ms. Ranking 10,000 in-memory records is 322.35 ms; worst bounded
deduplication is 342.89 ms at 200 records. The real mixed `open data` session completed in 3,062 ms;
GitHub was internally usable at 333 ms, GDELT was the 3,001 ms slowest connector, two sources returned
records, one source completed empty, and two were degraded/unavailable. The Arabic session completed
in 3,048.86 ms with 9 real GitHub matches.

## Validation

- Exact final backend/frontend/Playwright counts are recorded by the independent gate in
  `reports/final-independent-verification.md`; the historical counts previously listed here are no
  longer used as current evidence.
- Ruff, frontend lint, TypeScript, and production Vite build: passed.
- Build: 2,769 modules transformed successfully.
- SQLite reset/integrity/foreign keys/FTS: passed; reset counts content 0, FTS 0.
- Doctor: no failures; `.env` absence is an actionable warning.
- `verify-sources`: exit 0; authentication/network/configuration states distinguished safely.
- Docker Compose: both images built, both services started on localhost, API/frontend probes passed,
  and a saved-search record survived a container restart through the named data volume.
- Startup: strict ports and both HTTP readiness probes passed; Playwright reported no browser console
  errors and no serious accessibility findings.

## Remaining Blockers

- At least three real social connectors need legitimate operator credentials and successful live
  end-to-end verification.
- Bluesky is inaccessible from the current environment due to HTTP 403.

## Exact Run Commands

```bash
cp .env.example .env
npm run install:all
npm run doctor
npm run verify-sources
./start.sh
# open http://127.0.0.1:5173
./stop.sh
```

Deterministic release checks are `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`,
`npm run test:e2e`, `npm run evaluate:search`, `npm run evaluate:holdout`, `npm run benchmark`, and
`npm run benchmark:evidence`. Live probing is explicit: `npm run verify:live`.

SOCIAL PILOT BLOCKED
