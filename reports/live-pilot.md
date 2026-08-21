# Live Pilot

## Scope

The pilot used only real public endpoints and an isolated SQLite database. No mock connector,
fallback fixture, or fabricated record was enabled. The mixed-family source set was Bluesky
(Social), GDELT/RSS (News), and GitHub/Hacker News (Developer/Community). The neutral queries were
`open data` and `العراق`.

## English Session

- Session: `ceb89e91-07e6-4547-aa7c-197d26c251a9`
- Status: partial success
- Total: 11 records, 10 unique, 1 duplicate, 11 clusters
- Distribution: Hacker News 8, GitHub 3
- Total stored search duration: 3,062 ms
- Internally available first successful connector: GitHub at 333 ms
- Connector collection completion: 3,009 ms; the current REST architecture returns after the
  bounded connector set completes and does not stream the earlier records to the browser.
- Engine phases: persistence 4.89 ms, deduplication 16.47 ms, ranking 6.53 ms, clustering 19.95 ms
- Exports: JSON 11 records; UTF-8 CSV 19,226 bytes; all source links passed HTTP(S) validation

| Source | State | Fetched | Schema valid | Query match | Final match | Attempts | Total latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bluesky | unavailable / HTTP 403 | 0 | 0 | 0 | 0 | 1 | 279 ms |
| Hacker News | healthy | 20 | 20 | 20 upstream candidates | 8 | 1 | 1,075 ms |
| GitHub | healthy | 20 | 20 | 20 upstream candidates | 3 | 1 | 333 ms |
| GDELT | degraded / timeout | 0 | 0 | 0 | 0 | 2 | 3,001 ms |
| RSS | healthy / no query match | 30 | 30 | 0 | 0 | 1 | 454 ms |

## Arabic Session

- Session: `ede4fdeb-5f7a-4c8f-8a8e-fa78a2966721`
- Status: partial success
- Total: 9 records, 9 unique, 0 duplicates, 9 clusters
- Distribution: GitHub 9
- Wall time: 3,048.86 ms; stored connector phase 3,021.65 ms
- Engine phases: persistence 10.30 ms, deduplication 1.96 ms, ranking 4.11 ms, clustering 4.50 ms
- Exports: JSON 9 records; UTF-8 CSV 4,145 bytes; all source links passed HTTP(S) validation
- Query diagnostics preserved the original `العراق`, normalized form, token sequence, and the
  conservative Arabic definite-article variant `عراق` with its reason.

## End-To-End Evidence

Both sessions completed connector execution, normalization, candidate filtering, persistence, FTS,
scoring, duplicate analysis, clustering, analytics, and JSON/CSV export. The opt-in live Playwright
case reopened the persisted English session through the actual API and frontend, rendered real
results and original links, opened Explain Score and diagnostics, exported JSON, switched to Arabic
immediately, verified `dir=auto` external content, and observed no browser console errors.

Social Reach is `null` and platform diversity is `0`, correctly reflecting that no social connector
returned a record. MIRSAD does not manufacture a social metric from Hacker News or GitHub records.

## RSS Investigation

The earlier `78 raw / 0 normalized` observation was not 78 validation failures. Reproduction against
the configured BBC World feed fetched 90 entries over three probes: 90 were schema-valid, 0 were
malformed, and 0 contained the exact query terms for `climate policy`, `open data`, or `العراق`.
Current session telemetry likewise shows 30 fetched, 30 schema-valid, and 0 query matches. The
pipeline now exposes fetched, schema-valid, query-matching, time-eligible, excluded, malformed, and
normalized stages separately. HTML descriptions are safely converted to text while original title
and description remain in provenance metadata. Regression tests cover a matching record, an exact
phrase miss, HTML content, timestamps, URLs, and partial feed failure.

## Pilot State

Hacker News and GitHub are fully live end-to-end supplemental sources. No social credential was
present, and credential-free Bluesky was blocked by HTTP 403 in this environment. Consequently this
is an engineering acceptance pilot, not evidence of three live social platforms.

## Final Independent Recheck

On 2026-08-09 the corrected pipeline was rerun through the local REST API with real Hacker News,
GitHub, RSS, and Bluesky sources for `open data`:

- Session `52ae77ae-2b6a-4d58-93bd-497f1390965f` completed partially in 1,461 ms.
- 25 records were retained (GitHub 19, Hacker News 6), 23 were unique, and 21 story clusters were
  persisted. Bluesky remained an explicit HTTP 403 warning.
- Hacker News fetched/validated/normalized 25 records in 1,368.72 ms and produced 11 local matches.
  GitHub fetched/validated/normalized 25 in 354.67 ms and produced 23 local matches.
- RSS fetched and validated 30 entries in 408.92 ms; zero matched the query. This is a query-filter
  result, not a normalization failure.
- JSON export was 54,291 bytes. CSV was 16,602 bytes and began with the UTF-8 BOM `EF BB BF`.
  Every exported original link passed the HTTP(S) safety check.
- The post-run database returned `integrity_check=ok`, no foreign-key violations, and equal content
  and FTS counts of 25.

This recheck did not change the pilot state: no social connector returned content.
