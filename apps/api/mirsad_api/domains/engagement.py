from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Number

PLATFORM_SCALES: dict[str, dict[str, float]] = {
    "x": {"likes": 500, "reposts": 100, "replies": 75, "quotes": 40, "views": 50_000},
    "threads": {"likes": 250, "replies": 50, "reposts": 50, "quotes": 25},
    "telegram": {"views": 25_000, "forwards": 100, "reactions": 300, "replies": 50},
    "reddit": {"score": 500, "comments": 150},
    "bluesky": {"likes": 35, "reposts": 15, "replies": 15, "quotes": 10},
    "mastodon": {"likes": 50, "reposts": 25, "replies": 20},
    "hacker_news": {"points": 45, "comments": 35},
    "github": {"stars": 500, "forks": 100, "comments": 50},
    "youtube": {"views": 100_000, "likes": 5_000, "comments": 1_000},
    "tiktok": {
        "views": 250_000,
        "likes": 15_000,
        "comments": 1_000,
        "shares": 1_000,
        "favorites": 3_000,
    },
    "instagram": {"likes": 5_000, "comments": 500},
    "gdelt": {"mentions": 25},
    "rss": {},
    "mock": {"likes": 30, "shares": 15, "comments": 10},
}


def normalize_engagement(source: str, metrics: Mapping[str, object]) -> float:
    scales = PLATFORM_SCALES.get(source, {})
    if not scales:
        return 0.0
    weighted: list[float] = []
    for metric, scale in scales.items():
        raw = metrics.get(metric)
        if not isinstance(raw, Number) or isinstance(raw, bool):
            continue
        value = float(raw)
        weighted.append(min(1.0, math.log1p(max(0, value)) / math.log1p(scale)))
    return round(100 * sum(weighted) / len(weighted), 2) if weighted else 0.0


SOCIAL_SOURCES = {
    "x",
    "threads",
    "telegram",
    "reddit",
    "youtube",
    "instagram",
    "tiktok",
    "facebook",
    "linkedin",
    "bluesky",
    "mastodon",
}


def social_reach(source: str, engagement: float, platform_diversity: int = 1) -> float | None:
    """Public distribution signal, not a reliability or truth assessment."""
    if source not in SOCIAL_SOURCES:
        return None
    diversity = 100 * (1 - math.exp(-max(0, platform_diversity - 1) / 2))
    return round(min(100.0, 0.8 * engagement + 0.2 * diversity), 2)
