from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from .query import normalize_text, tokenize

ENGLISH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}
ARABIC_STOPWORDS = {
    "اذ",
    "اذا",
    "الى",
    "ان",
    "او",
    "اي",
    "بها",
    "به",
    "بين",
    "تلك",
    "ثم",
    "هذا",
    "هذه",
    "ذلك",
    "عن",
    "علي",
    "في",
    "كان",
    "كما",
    "لا",
    "ما",
    "مع",
    "من",
    "هو",
    "هي",
    "و",
    "يا",
}
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

BUCKETS = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def time_buckets(
    dates: list[datetime],
    *,
    bucket: str = "1h",
    bucket_count: int = 12,
    now: datetime | None = None,
    window_start: datetime | None = None,
) -> list[dict[str, Any]]:
    step = BUCKETS.get(bucket, BUCKETS["1h"])
    bucket_count = max(1, min(366, bucket_count))
    current = now or datetime.now(UTC)
    current = _aware(current)
    if window_start is not None:
        window_start = _aware(window_start)
        span_seconds = max(1.0, (current - window_start).total_seconds())
        step = timedelta(seconds=span_seconds / bucket_count)
    else:
        window_start = current - step * bucket_count
    counts = [0] * bucket_count
    for date in dates:
        date = _aware(date)
        if window_start <= date <= current:
            index = min(bucket_count - 1, int((date - window_start) / step))
            counts[index] += 1
    return [
        {"timestamp": (window_start + step * index).isoformat(), "count": count}
        for index, count in enumerate(counts)
    ]


def trend_indicator(timeline: list[dict[str, Any]]) -> float:
    values = [int(point["count"]) for point in timeline]
    midpoint = len(values) // 2
    baseline = sum(values[:midpoint]) / max(1, midpoint)
    current = sum(values[midpoint:]) / max(1, len(values) - midpoint)
    if baseline == 0:
        return 100.0 if current > 0 else 0.0
    return round(max(-100, min(500, ((current - baseline) / baseline) * 100)), 2)


def build_analytics(
    items: list[dict[str, Any]],
    *,
    unique_count: int,
    duration_ms: int,
    cluster_sizes: list[int],
    query_tokens: tuple[str, ...] = (),
    bucket: str = "1h",
    bucket_count: int = 12,
    include_all_time: bool = False,
) -> dict[str, Any]:
    # Persisted content can legitimately exist without a query-specific score
    # (for example, a manual import). Average and distribution metrics only
    # describe records that actually have score evidence.
    scores = [float(item["score"]) for item in items if item.get("score") is not None]
    dates = [item["published_at"] for item in items if item.get("published_at")]
    common_window_start = min((_aware(value) for value in dates), default=None)
    if not include_all_time:
        common_window_start = None
    timeline = time_buckets(
        dates,
        bucket=bucket,
        bucket_count=bucket_count,
        window_start=common_window_start,
    )
    social_items = [item for item in items if item.get("category") == "social"]
    news_items = [item for item in items if item.get("category") == "news"]
    social_timeline = time_buckets(
        [item["published_at"] for item in social_items if item.get("published_at")],
        bucket=bucket,
        bucket_count=bucket_count,
        window_start=common_window_start,
    )
    news_timeline = time_buckets(
        [item["published_at"] for item in news_items if item.get("published_at")],
        bucket=bucket,
        bucket_count=bucket_count,
        window_start=common_window_start,
    )
    score_ranges = Counter()
    for score in scores:
        start = min(80, int(score // 20) * 20)
        score_ranges["80-100" if start == 80 else f"{start}-{start + 19}"] += 1
    excluded = ENGLISH_STOPWORDS | ARABIC_STOPWORDS | set(query_tokens)
    term_counts: Counter[str] = Counter()
    for item in items:
        content = URL_PATTERN.sub(" ", f"{item.get('title') or ''} {item.get('text') or ''}")
        terms = {
            normalize_text(token.removeprefix("#"))
            for token in tokenize(content)
            if len(token) > 2 and normalize_text(token) not in excluded
        }
        term_counts.update(term for term in terms if term and term not in excluded)
    sources = Counter(str(item["source"]) for item in items)
    social_sources = Counter(str(item["source"]) for item in social_items)
    categories = Counter(str(item.get("category", "developer_community")) for item in items)
    hashtags = Counter(
        str(tag).casefold()
        for item in social_items
        for tag in (item.get("hashtags") or [])
        if str(tag).strip()
    )
    mentions = Counter(
        str(account).casefold()
        for item in social_items
        for account in (item.get("mentions") or [])
        if str(account).strip()
    )
    engaged = sorted(
        (
            {
                "id": item.get("id"),
                "source": item["source"],
                "title": item.get("title"),
                "engagement": item.get("engagement", 0),
                "social_reach": item.get("social_reach"),
            }
            for item in social_items
            if item.get("engagement") is not None and item.get("has_engagement_metrics")
        ),
        key=lambda item: float(item["engagement"] or 0),
        reverse=True,
    )[:10]
    current = datetime.now(UTC)
    publication_distribution = Counter()
    for item in items:
        published = item.get("published_at")
        if not published:
            publication_distribution["unavailable"] += 1
            continue
        age = current - _aware(published)
        label = (
            "last_24h"
            if age <= timedelta(days=1)
            else "last_7d"
            if age <= timedelta(days=7)
            else "last_30d"
            if age <= timedelta(days=30)
            else "older"
        )
        publication_distribution[label] += 1
    return {
        "total_results": len(items),
        "unique_results": unique_count,
        "source_count": len(sources),
        "duplicate_count": len(items) - unique_count,
        "average_score": round(sum(scores) / max(1, len(scores)), 2),
        "search_duration_ms": duration_ms,
        "mentions_over_time": timeline,
        "trend_percent": trend_indicator(timeline),
        "overall_trend_percent": trend_indicator(timeline),
        "social_mentions_over_time": social_timeline,
        "social_trend_percent": trend_indicator(social_timeline),
        "news_mentions_over_time": news_timeline,
        "news_trend_percent": trend_indicator(news_timeline),
        "platform_distribution": dict(sources),
        "social_source_distribution": dict(social_sources),
        "most_active_platforms": [
            {"source": source, "count": count} for source, count in social_sources.most_common()
        ],
        "most_engaged_results": engaged,
        "top_hashtags": [
            {"term": term, "count": count} for term, count in hashtags.most_common(12)
        ],
        "top_mentioned_accounts": [
            {"term": term, "count": count} for term, count in mentions.most_common(12)
        ],
        "platform_diversity": len(social_sources),
        "category_distribution": dict(categories),
        "average_social_reach": (
            round(
                sum(
                    float(item["social_reach"])
                    for item in social_items
                    if item.get("social_reach") is not None
                )
                / len([item for item in social_items if item.get("social_reach") is not None]),
                2,
            )
            if any(item.get("social_reach") is not None for item in social_items)
            else None
        ),
        "top_related_terms": [
            {"term": term, "count": count} for term, count in term_counts.most_common(12)
        ],
        "language_distribution": dict(Counter(str(item["language"]) for item in items)),
        "publication_time_distribution": dict(publication_distribution),
        "score_distribution": dict(sorted(score_ranges.items())),
        "cluster_distribution": dict(Counter(str(size) for size in cluster_sizes)),
        "bucket": "adaptive" if common_window_start is not None else bucket,
        "bucket_count": bucket_count,
    }
