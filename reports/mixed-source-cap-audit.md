# Mixed-Source Global Cap Audit

## Method

This deterministic audit executes the real SearchService, SQLite FTS5, and the installed local multilingual MiniLM. Six source-shaped connectors each receive a bounded pre-candidate opportunity. The final cap of 30 is applied only after the union is scored. Each query is repeated with both source request order and connector completion order reversed. Uneven final source composition is retained; the audit does not impose source quotas.

Queries: 11. Source pre-candidate limit: 50. Semantic rerank limit: 20. Final cap: 30.

## Per-Query Evidence

### `artificial intelligence`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=4, github=5, hacker_news=5, rss=5
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 81.12, "mean": 71.701, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 76.7}, "github": {"count": 8, "max": 99.88, "mean": 82.495, "median": 85.23, "min": 66.79, "p25": 66.895, "p75": 91.952}, "hacker_news": {"count": 8, "max": 99.82, "mean": 82.42, "median": 85.21, "min": 66.65, "p25": 66.755, "p75": 91.922}, "mastodon": {"count": 8, "max": 81.12, "mean": 71.701, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 76.7}, "rss": {"count": 8, "max": 99.76, "mean": 81.698, "median": 85.23, "min": 66.79, "p25": 66.895, "p75": 90.387}, "youtube": {"count": 8, "max": 99.76, "mean": 81.698, "median": 85.23, "min": 66.79, "p25": 66.895, "p75": 90.387}}`

### `open source`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=4, github=5, hacker_news=5, rss=5
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 82.66, "mean": 71.711, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 75.965}, "github": {"count": 8, "max": 99.88, "mean": 82.407, "median": 84.465, "min": 66.79, "p25": 66.895, "p75": 92.575}, "hacker_news": {"count": 8, "max": 99.82, "mean": 82.335, "median": 84.455, "min": 66.65, "p25": 66.755, "p75": 92.545}, "mastodon": {"count": 8, "max": 82.66, "mean": 71.711, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 75.965}, "rss": {"count": 8, "max": 99.76, "mean": 81.349, "median": 84.465, "min": 66.79, "p25": 66.895, "p75": 90.488}, "youtube": {"count": 8, "max": 99.76, "mean": 81.349, "median": 84.465, "min": 66.79, "p25": 66.895, "p75": 90.488}}`

### `climate adaptation`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=4, github=5, hacker_news=5, rss=5
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 85.09, "mean": 73.748, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 83.64}, "github": {"count": 8, "max": 99.88, "mean": 84.519, "median": 91.48, "min": 66.79, "p25": 66.895, "p75": 94.72}, "hacker_news": {"count": 8, "max": 99.82, "mean": 84.445, "median": 91.465, "min": 66.65, "p25": 66.755, "p75": 94.69}, "mastodon": {"count": 8, "max": 85.09, "mean": 73.748, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 83.64}, "rss": {"count": 8, "max": 99.76, "mean": 84.024, "median": 91.48, "min": 66.79, "p25": 66.895, "p75": 93.76}, "youtube": {"count": 8, "max": 99.76, "mean": 84.024, "median": 91.48, "min": 66.79, "p25": 66.895, "p75": 93.76}}`

### `public health`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=3, github=5, hacker_news=5, rss=6
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 83.97, "mean": 72.898, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 79.65}, "github": {"count": 8, "max": 99.88, "mean": 85.588, "median": 88.825, "min": 66.79, "p25": 74.395, "p75": 93.865}, "hacker_news": {"count": 8, "max": 99.82, "mean": 85.516, "median": 88.815, "min": 66.65, "p25": 74.255, "p75": 93.843}, "mastodon": {"count": 8, "max": 83.97, "mean": 72.898, "median": 68.41, "min": 66.79, "p25": 66.895, "p75": 79.65}, "rss": {"count": 8, "max": 99.76, "mean": 84.67, "median": 88.825, "min": 66.79, "p25": 74.395, "p75": 92.06}, "youtube": {"count": 8, "max": 99.76, "mean": 84.67, "median": 88.825, "min": 66.79, "p25": 74.395, "p75": 92.06}}`

### `technology`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=4, github=5, hacker_news=5, rss=5
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 77.14, "mean": 70.28, "median": 68.505, "min": 66.81, "p25": 66.922, "p75": 73.142}, "github": {"count": 8, "max": 99.87, "mean": 81.045, "median": 81.565, "min": 66.81, "p25": 66.922, "p75": 88.71}, "hacker_news": {"count": 8, "max": 99.81, "mean": 80.969, "median": 81.55, "min": 66.66, "p25": 66.773, "p75": 88.688}, "mastodon": {"count": 8, "max": 77.14, "mean": 70.28, "median": 68.505, "min": 66.81, "p25": 66.922, "p75": 73.142}, "rss": {"count": 8, "max": 99.75, "mean": 79.603, "median": 81.565, "min": 66.81, "p25": 66.922, "p75": 85.855}, "youtube": {"count": 8, "max": 99.75, "mean": 79.603, "median": 81.565, "min": 66.81, "p25": 66.922, "p75": 85.855}}`

### `#technology`

- Matched: youtube=8, bluesky=6, mastodon=6, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=6, mastodon=6, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=3, github=5, hacker_news=5, rss=6
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 6, "max": 68.86, "mean": 67.748, "median": 67.66, "min": 66.79, "p25": 66.828, "p75": 68.642}, "github": {"count": 8, "max": 100, "mean": 87.502, "median": 99.81, "min": 66.79, "p25": 66.903, "p75": 99.94}, "hacker_news": {"count": 8, "max": 99.94, "mean": 87.406, "median": 99.75, "min": 66.64, "p25": 66.752, "p75": 99.87}, "mastodon": {"count": 6, "max": 68.86, "mean": 67.748, "median": 67.66, "min": 66.79, "p25": 66.828, "p75": 68.642}, "rss": {"count": 8, "max": 100, "mean": 87.502, "median": 99.81, "min": 66.79, "p25": 66.903, "p75": 99.94}, "youtube": {"count": 8, "max": 100, "mean": 87.502, "median": 99.81, "min": 66.79, "p25": 66.903, "p75": 99.94}}`

### `بغداد`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=4, github=5, hacker_news=5, rss=5
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 85.84, "mean": 73.189, "median": 68.48, "min": 66.77, "p25": 66.882, "p75": 79.657}, "github": {"count": 8, "max": 99.87, "mean": 83.787, "median": 88.34, "min": 66.77, "p25": 66.882, "p75": 95.097}, "hacker_news": {"count": 8, "max": 99.81, "mean": 83.71, "median": 88.32, "min": 66.62, "p25": 66.733, "p75": 95.075}, "mastodon": {"count": 8, "max": 85.84, "mean": 73.189, "median": 68.48, "min": 66.77, "p25": 66.882, "p75": 79.657}, "rss": {"count": 8, "max": 99.74, "mean": 83.2, "median": 88.34, "min": 66.77, "p25": 66.882, "p75": 93.955}, "youtube": {"count": 8, "max": 99.74, "mean": 83.2, "median": 88.34, "min": 66.77, "p25": 66.882, "p75": 93.955}}`

### `الذكاء الاصطناعي`

- Matched: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=8, mastodon=8, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=4, github=5, hacker_news=5, rss=5
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 8, "max": 83.61, "mean": 72.373, "median": 68.365, "min": 66.72, "p25": 66.825, "p75": 78.555}, "github": {"count": 8, "max": 99.87, "mean": 83.05, "median": 86.42, "min": 66.72, "p25": 66.825, "p75": 93.668}, "hacker_news": {"count": 8, "max": 99.81, "mean": 82.972, "median": 86.4, "min": 66.57, "p25": 66.683, "p75": 93.638}, "mastodon": {"count": 8, "max": 83.61, "mean": 72.373, "median": 68.365, "min": 66.72, "p25": 66.825, "p75": 78.555}, "rss": {"count": 8, "max": 99.75, "mean": 82.427, "median": 86.42, "min": 66.72, "p25": 66.825, "p75": 92.453}, "youtube": {"count": 8, "max": 99.75, "mean": 82.427, "median": 86.42, "min": 66.72, "p25": 66.825, "p75": 92.453}}`

### `#بغداد`

- Matched: youtube=8, bluesky=6, mastodon=6, github=8, hacker_news=8, rss=8
- Candidate admitted: youtube=8, bluesky=6, mastodon=6, github=8, hacker_news=8, rss=8
- Final top 30: youtube=8, bluesky=3, mastodon=3, github=5, hacker_news=5, rss=6
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 6, "max": 68.85, "mean": 67.728, "median": 67.64, "min": 66.76, "p25": 66.8, "p75": 68.63}, "github": {"count": 8, "max": 100, "mean": 87.491, "median": 99.805, "min": 66.76, "p25": 66.88, "p75": 99.94}, "hacker_news": {"count": 8, "max": 99.94, "mean": 87.396, "median": 99.745, "min": 66.62, "p25": 66.725, "p75": 99.87}, "mastodon": {"count": 6, "max": 68.85, "mean": 67.728, "median": 67.64, "min": 66.76, "p25": 66.8, "p75": 68.63}, "rss": {"count": 8, "max": 100, "mean": 87.491, "median": 99.805, "min": 66.76, "p25": 66.88, "p75": 99.94}, "youtube": {"count": 8, "max": 100, "mean": 87.491, "median": 99.805, "min": 66.76, "p25": 66.88, "p75": 99.94}}`

### `Microsoft العراق`

- Matched: youtube=16, bluesky=16, mastodon=16, github=16, hacker_news=16, rss=16
- Candidate admitted: youtube=16, bluesky=16, mastodon=16, github=16, hacker_news=16, rss=16
- Final top 30: youtube=11, bluesky=3, mastodon=3, github=4, hacker_news=3, rss=6
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss, youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube, rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 16, "max": 86.38, "mean": 70.209, "median": 68.37, "min": 66.72, "p25": 66.833, "p75": 68.6}, "github": {"count": 16, "max": 99.94, "mean": 85.263, "median": 89.535, "min": 66.72, "p25": 66.833, "p75": 99.87}, "hacker_news": {"count": 16, "max": 99.87, "mean": 85.177, "median": 89.515, "min": 66.58, "p25": 66.685, "p75": 99.81}, "mastodon": {"count": 16, "max": 86.38, "mean": 70.209, "median": 68.37, "min": 66.72, "p25": 66.833, "p75": 68.6}, "rss": {"count": 16, "max": 99.94, "mean": 84.358, "median": 85.955, "min": 66.72, "p25": 66.833, "p75": 99.78}, "youtube": {"count": 16, "max": 99.94, "mean": 84.358, "median": 85.955, "min": 66.72, "p25": 66.833, "p75": 99.78}}`

### `AI بغداد`

- Matched: youtube=16, bluesky=16, mastodon=16, github=16, hacker_news=16, rss=16
- Candidate admitted: youtube=16, bluesky=16, mastodon=16, github=16, hacker_news=16, rss=16
- Final top 30: youtube=11, bluesky=3, mastodon=3, github=4, hacker_news=3, rss=6
- Semantic top-20 opportunity: youtube=4, bluesky=3, mastodon=3, github=3, hacker_news=3, rss=4
- Completion A: youtube, bluesky, mastodon, github, hacker_news, rss, youtube, bluesky, mastodon, github, hacker_news, rss
- Completion B: rss, hacker_news, github, mastodon, bluesky, youtube, rss, hacker_news, github, mastodon, bluesky, youtube
- Final identities/order unchanged: True
- Relevance distributions: `{"bluesky": {"count": 16, "max": 86.67, "mean": 70.87, "median": 68.375, "min": 66.73, "p25": 66.843, "p75": 68.6}, "github": {"count": 16, "max": 99.94, "mean": 85.93, "median": 93.275, "min": 66.73, "p25": 66.843, "p75": 99.87}, "hacker_news": {"count": 16, "max": 99.87, "mean": 85.845, "median": 93.26, "min": 66.59, "p25": 66.695, "p75": 99.81}, "mastodon": {"count": 16, "max": 86.67, "mean": 70.87, "median": 68.375, "min": 66.73, "p25": 66.843, "p75": 68.6}, "rss": {"count": 16, "max": 99.94, "mean": 85.181, "median": 90.65, "min": 66.73, "p25": 66.843, "p75": 99.78}, "youtube": {"count": 16, "max": 99.94, "mean": 85.181, "median": 90.65, "min": 66.73, "p25": 66.843, "p75": 99.78}}`

## Finding

The initial audit identified a source-scale discontinuity at the bounded semantic stage: title-bearing records consumed the global top-20 lexical slots while comparable titleless social posts retained lexical-only scores. The top-20 limit and 25/75 fusion remain unchanged; selection now cycles deterministically through each source's lexical queue before global scoring. This allocates evaluation opportunity and does not reserve final positions.

All matched sources retained their independently bounded admission opportunity. The global result cap was applied after FTS/BM25, unchanged bounded semantic reranking, explainable scoring, and duplicate-aware ordering. Connector completion order did not affect final result identity or order. Source distributions were not equalized.

MIXED-SOURCE CAP VERIFIED
