# Changelog

## MIRSAD 1.1.1 - 2026-08-21

- Separates content platform from per-search acquisition path so local-memory evidence cannot masquerade as a live connector execution; adds truthful local-memory SSE and acquisition-funnel diagnostics.
- Narrows deterministic `PERSON_LIKE` intent evidence for Arabic/English topic and organization phrases while preserving tested Arabic person names and literal handles, hashtags, and identifiers.
- Overlaps one bounded, non-fatal semantic-preparation worker with connector I/O through the existing authoritative cache; final candidate admission, 25/75 scoring, top-20 opportunity, and ordering remain unchanged.
- Makes terminal searches results-first while preserving the three-panel active trace, and redesigns Explain Score around the real 25% lexical / 75% semantic core plus the at-most-1% secondary adjustment.
- Adds scoped GSAP state motion, an accessible runtime-backed SVG flow, and one lazy disposable Three.js topology with reduced-motion, visibility, context-loss, and static fallback behavior.

Known limitations: external collection remains the dominant variable; Bluesky AppView may return an
environment-specific `403`, and optional SearXNG remains disabled by default. Three.js is a lazy optional
visual layer and adds a separate compressed chunk; search and trace remain fully functional through SVG.

## MIRSAD 1.1.0 - 2026-08-21

- Evolves Search into a responsive analyst workspace with immediate feedback, live source progress, contextual Results/Clusters/Timeline/Analysis views, compact density, and safe relevant-term highlighting.
- Adds bounded expiring search jobs and a typed server-sent event protocol while retaining the synchronous search API and authoritative frozen final ranking.
- Adds phase-level semantic profiling and verifies the existing bounded model/content caches and batch encoding; no persistent embedding store or new database is introduced.
- Records per-source retrieval funnels and existing shadow utility comparisons without allowing shadow recommendations to change production routing.
- Hardens exact identifier admission so punctuation-preserving CVE/GHSA/repository identifiers cannot admit records that merely share broad identifier tokens.
- Preserves MAFER Phase 2 production ranking, local operator data, Arabic/English behavior, and optional/disabled web-discovery semantics.

Known limitations: final completion time still depends primarily on external connector latency and cold
local model initialization; Bluesky, GitHub, and GDELT can be externally access-limited; SearXNG remains
optional and disabled by default. Search cancellation is not exposed because the current persisted search
transaction is deliberately allowed to finish safely after an SSE client disconnects.

## MIRSAD 1.0.0 - 2026-08-10

- Ships the verified deterministic MAFER Phase 2 production planner with bounded Fast, Balanced, and Deep search modes.
- Preserves 25% lexical / 75% local multilingual MiniLM relevance over at most 20 semantic candidates and a 1% secondary-quality budget.
- Supports direct/public YouTube, Bluesky, Mastodon, GitHub, Hacker News, RSS, and GDELT collection with isolated source failures.
- Adds capability-honest X, Threads, and Reddit web-index discovery through optional localhost SearXNG plus an explicit non-fetching browser capture fallback.
- Provides Arabic/English search and RTL/LTR UI, provenance, diagnostics, exports, duplicate groups, hardened story clusters, saved searches, and bookmarks.
- Records local explicit relevance feedback and Phase 3 adaptive comparisons in shadow mode; no adaptive strategy is promoted in 1.0.0.

Known limitations: external web engines may rate-limit or require CAPTCHA; direct platform APIs still
require legitimate credentials/approval; Mastodon public coverage is instance-scoped; Arabic known-item
loss remains concentrated in external rediscovery, especially handle lookup. MIRSAD neither bypasses
access controls nor interprets Social Reach, source confidence, or discovery support as truth.
