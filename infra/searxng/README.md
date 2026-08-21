# Local SearXNG

This optional service supplies MAFER web-index discovery. It is not authoritative content storage
and the browser never communicates with it directly.

```bash
cp infra/searxng/.env.example infra/searxng/.env
docker compose --env-file infra/searxng/.env -f infra/searxng/compose.yml up -d
```

Set `SEARXNG_ENABLED=true` and `SEARXNG_URL=http://127.0.0.1:8080` in the root `.env`, then run
`npm run verify-sources`. JSON output is explicitly enabled. The configured engines are bounded,
credential-free defaults; upstream 403, 429, CAPTCHA, and timeout states are recorded and are not
circumvented.

MIRSAD uses this service only to discover candidate public URLs. It independently validates X,
Threads, and Reddit hosts and content-path types and never fetches an arbitrary result URL. Stop the
service with:

```bash
docker compose --env-file infra/searxng/.env -f infra/searxng/compose.yml down
```
