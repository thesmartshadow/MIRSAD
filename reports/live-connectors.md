# Live Connector Verification

Generated: 2026-08-09T01:24:13.683014+00:00

| Connector | State | Probes | Fetched | Matched | Normalized | Latency | Limitation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| X | unconfigured | 0 | 0 | 0 | 0 | 0 ms | Bearer token not configured |
| Threads | unconfigured | 0 | 0 | 0 | 0 | 0 ms | Access token not configured |
| Telegram | unconfigured | 0 | 0 | 0 | 0 | 0 ms | Public-channel user session not configured |
| Reddit | unconfigured | 0 | 0 | 0 | 0 | 0 ms | Approved API credentials required |
| Bluesky | unavailable | 3 | 0 | 0 | 0 | 831 ms | http_403 |
| Hacker News | healthy | 3 | 10 | 10 | 10 | 2048 ms | None observed |
| GitHub | healthy | 3 | 11 | 11 | 11 | 1675 ms | Anonymous requests have a lower rate limit |
| GDELT News | degraded | 3 | 0 | 0 | 0 | 6004 ms | circuit_open, timeout |
| RSS Feeds | healthy | 3 | 90 | 0 | 0 | 1127 ms | None observed |
| YouTube | unconfigured | 0 | 0 | 0 | 0 | 0 ms | API key not configured |
| Mastodon | unconfigured | 0 | 0 | 0 | 0 | 0 ms | Instance URL and user access token not configured |
| Instagram | unconfigured | 0 | 0 | 0 | 0 | 0 ms | Professional account hashtag access not configured |
| TikTok | restricted | 0 | 0 | 0 | 0 | 0 ms | Research API approval and credentials required |
| Facebook | restricted | 0 | 0 | 0 | 0 | 0 ms | Global public-post keyword search is not available with the configured API access |
| LinkedIn | restricted | 0 | 0 | 0 | 0 | 0 ms | Global public-post search is unavailable through configured API access |

This report reflects one environment and time. Live verification is supplemental and is not a CI dependency.
