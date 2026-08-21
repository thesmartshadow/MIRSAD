# MIRSAD Engineering Rules

## Architecture

- Keep the monorepo split between `apps/web` (React, TypeScript, Vite) and `apps/api` (FastAPI, SQLAlchemy, SQLite).
- Preserve backend domain boundaries for connectors, query processing, normalization, ranking, deduplication, clustering, analytics, persistence, schemas, configuration, and health.
- Keep the product local-first. Bind services to localhost by default and never introduce a required hosted dependency.
- Use SQLite FTS5 for the lexical index. Explainable deterministic ranking is the default; opaque AI must never replace it.

## Frontend

- shadcn/ui is the only component system. Tailwind may style layout around shadcn components; Lucide, TanStack Table, and Recharts under shadcn Charts are allowed.
- Do not add Material UI, Ant Design, Chakra, Mantine, Bootstrap, DaisyUI, Flowbite, PrimeReact, or another component library.
- All visible strings must use the localization layer. Arabic is RTL and English is LTR; direction is set at the application provider/root, not by page-specific mirroring.
- Use design tokens and CSS variables. Preserve the restrained institutional visual language and avoid gradients, glass effects, and decorative animation.

## Data And Connectors

- Every connector implements `BaseConnector`: metadata, configuration validation, health check, search, and normalization.
- Capability metadata is the source of truth for search modes, taxonomy, credential/approval requirements, and frontend availability. Do not hardcode platform capability claims in pages.
- Preserve the source taxonomy: Social, News, and Developer/Community. Restricted connector adapters must state unsupported global-search behavior and must not scrape as a substitute.
- Connector calls have fixed hosts, explicit timeouts, bounded retries, rate-limit handling, structured failures, and latency metrics.
- Keep source/platform separate from `acquisition_mode`. Web-index records must remain labeled `WEB_INDEX` and must never be presented as direct platform API responses.
- MAFER discovery uses backend-configured SearXNG/Common Crawl endpoints and strict platform URL classifiers. Never trust `site:` alone, fetch arbitrary result URLs, or use CAPTCHA/proxy/login circumvention.
- Isolate connector failures. A partial source failure must not fail the full search.
- Never fabricate external data. Deterministic fixtures and mock connectors are permitted only in tests or explicit local demo mode.
- Preserve original retrieved text and source provenance. Deduplication groups records; it does not delete originals.
- Missing external engagement metrics remain null/absent. Never coerce an unavailable public metric to zero.
- Secrets stay server-side and must never appear in API responses, logs, frontend code, or committed `.env` files.

## Quality

- Add deterministic tests for changes to queries, ranking, connectors, persistence, API behavior, localization, and important UI flows.
- Do not consider work complete until backend tests/lint, frontend tests/lint/typecheck, the production build, database initialization, and a startup smoke test pass.
- Update documentation when behavior, configuration, connectors, scoring, or the API changes.
