# Social connector credentials

MIRSAD reads connector credentials only in the FastAPI process. The browser receives configuration states, never credential values. Empty values are treated as absent. `npm run verify-sources` performs the least expensive access check implemented for each configured connector and does not print request headers, tokens, client secrets, API hashes, or session strings.

The table below documents direct platform credentials. When the backend-only `SEARXNG_ENABLED=true` and `SEARXNG_URL` point to the local service, X, Threads, and Reddit can operate in `WEB_INDEX` mode without those platform credentials. That mode validates indexed public URLs and does not claim direct API search, permissions, live completeness, or platform engagement metrics.

## Configuration matrix

| Connector | Environment fields read by MIRSAD | Secret values | Authorization model | Approval/access prerequisite | Token lifecycle in the current code | Minimum access used by the adapter | Validation request |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| X | `X_BEARER_TOKEN`; optional `MIRSAD_X_ARCHIVE_ACCESS` | 1 | App-only bearer token; MIRSAD does not run an OAuth consent flow | Approved developer app and an access tier that permits recent search; full archive is independently conditional | Static operator-supplied token; no refresh implementation | `GET /2/tweets/search/recent`; full archive only when explicitly enabled | One recent-search request with `max_results=10`, the API minimum |
| Threads | `THREADS_ACCESS_TOKEN` | 1 | Threads user access token obtained outside MIRSAD | Meta app/user authorization; the search path needs `threads_basic` and `threads_keyword_search` | Static operator-supplied token; MIRSAD does not exchange, extend, or refresh it | `GET /keyword_search` with keyword or tag mode | `GET /me?fields=id` |
| Telegram | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING` | 3 | MTProto application credentials plus an already authorized user session; not OAuth and not a Bot API token | Telegram application registration and one interactive user authorization performed outside MIRSAD | The serialized user session is reused; MIRSAD neither signs in nor refreshes it | `channels.searchPosts` for public broadcast channels with public usernames only | Connect and call `is_user_authorized`; no post search |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`; non-secret `MIRSAD_REDDIT_USER_AGENT` | 2 | OAuth 2 client-credentials grant | Registered/approved Data API use under Reddit's current terms | A short-lived app token is requested for every validation and search; no refresh token is used | Read-only OAuth listing search at `/search` or a configured community search | OAuth token request only |
| YouTube | `YOUTUBE_API_KEY` | 1 | Google API key for public data; no OAuth user authorization | Google project with YouTube Data API v3 enabled and available quota | Static API key; no token refresh | Public `search.list` plus `videos.list` statistics | `i18nLanguages.list`, avoiding the 100-unit search call |
| Mastodon | `MASTODON_PUBLIC_INSTANCES` for credential-free mode; optional `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` for full-text mode | No credential for public timelines; authenticated mode uses 1 token plus instance URL | Optional instance-issued user OAuth token | Public preview must be enabled for credential-free timelines. Authenticated full-text recall depends on the configured instance search backend | Static operator-supplied token; no refresh implementation | Public `GET /api/v1/timelines/public` and `/api/v1/timelines/tag/:hashtag`; authenticated `GET /api/v2/search?type=statuses` | Public mode probes `/api/v1/timelines/public?limit=1`; authenticated mode uses `/api/v1/accounts/verify_credentials` |
| Instagram | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`; optional `MIRSAD_META_GRAPH_VERSION` | 1 token plus account ID | Meta user or system-user access token for the Instagram API with Facebook Login | Professional account, linked Page where required, app roles/review and access level appropriate to the operator's accounts | Static operator-supplied token; no exchange or refresh implementation | `ig_hashtag_search` and `{hashtag-id}/recent_media` only; no global keyword search. The code does not request or inspect scopes; provision the permissions Meta currently requires for these two endpoints, normally including basic Instagram/Page read access | `GET /{version}/{instagram-user-id}?fields=id` |
| TikTok | `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `MIRSAD_TIKTOK_RESEARCH_APPROVED=true` | 2 | Research API client-credentials grant | TikTok Research API project approval is mandatory | TikTok client tokens expire after two hours; MIRSAD requests a new token for every validation/search and does not use a refresh token | Approved Research API video query | Client-token request only |

`MIRSAD_REDDIT_USER_AGENT` is required by the connector but is an application identifier, not a secret. `MASTODON_BASE_URL` and `INSTAGRAM_USER_ID` identify a server/account and are not authentication secrets, but MIRSAD still does not return them as connector configuration values.

## Operational states

- `PASS` means the implemented access check completed, or a credential-free connector's local configuration is valid.
- `WARN` means an optional connector is unconfigured/restricted, quota-exhausted, or rate-limited. These conditions do not make the local MIRSAD installation fail.
- `FAIL` means configured credentials were rejected, the configured endpoint was unavailable, or the validation request could not complete.
- The command exits non-zero only for a MIRSAD registry/validation implementation failure. Optional credential and network failures remain visible in output and the JSON report but do not break automation.

The command writes `reports/source-verification.json`. Use `npm run verify:live` separately for real query/normalization verification; credential validation is not proof that a platform search entitlement or quota will return records.

## Platform references

- X recent search: <https://docs.x.com/x-api/posts/search/quickstart/recent-search>
- Threads official API collection and keyword search: <https://www.postman.com/meta/threads/overview> and <https://www.postman.com/meta/threads/request/m9j4i2x/search-for-threads-posts>
- Telegram application credentials and user authorization: <https://core.telegram.org/api/obtaining_api_id> and <https://core.telegram.org/api/auth>
- Reddit Data API terms: <https://redditinc.com/policies/data-api-terms>
- YouTube Data API authentication: <https://developers.google.com/youtube/v3/docs>
- Mastodon search and `read:search`: <https://docs.joinmastodon.org/methods/search/>
- Meta's official Instagram API collection: <https://www.postman.com/meta/instagram/overview>
- TikTok Research API setup and client tokens: <https://developers.tiktok.com/doc/research-api-get-started> and <https://developers.tiktok.com/doc/client-access-token-management>
