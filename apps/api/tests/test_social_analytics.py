from datetime import UTC, datetime, timedelta

from mirsad_api.domains.analytics import build_analytics, time_buckets


def test_social_analytics_preserves_missing_engagement_and_score_bucket() -> None:
    analytics = build_analytics(
        [
            {
                "id": "social-without-metrics",
                "source": "youtube",
                "category": "social",
                "title": "Baghdad public channel",
                "text": "Baghdad public channel",
                "language": "en",
                "published_at": datetime.now(UTC),
                "score": 100,
                "engagement": None,
                "has_engagement_metrics": False,
                "social_reach": None,
                "hashtags": None,
                "mentions": None,
            }
        ],
        unique_count=1,
        duration_ms=5,
        cluster_sizes=[1],
        query_tokens=("baghdad",),
    )

    assert analytics["most_engaged_results"] == []
    assert analytics["average_social_reach"] is None
    assert analytics["score_distribution"] == {"80-100": 1}


def test_analytics_window_does_not_silently_drop_seven_day_records() -> None:
    now = datetime(2026, 8, 8, tzinfo=UTC)
    timeline = time_buckets(
        [now - timedelta(days=6)], bucket="6h", bucket_count=28, now=now
    )
    assert len(timeline) == 28
    assert sum(point["count"] for point in timeline) == 1


def test_all_time_analytics_adapts_to_the_oldest_stored_record() -> None:
    now = datetime.now(UTC)
    analytics = build_analytics(
        [
            {
                "id": "old",
                "source": "rss",
                "category": "news",
                "title": "Historical policy archive",
                "text": "Historical policy archive",
                "language": "en",
                "published_at": now - timedelta(days=900),
                "score": 50,
                "hashtags": None,
                "mentions": None,
            },
            {
                "id": "new",
                "source": "rss",
                "category": "news",
                "title": "Current policy archive",
                "text": "Current policy archive",
                "language": "en",
                "published_at": now,
                "score": 60,
                "hashtags": None,
                "mentions": None,
            },
        ],
        unique_count=2,
        duration_ms=1,
        cluster_sizes=[1, 1],
        include_all_time=True,
        bucket_count=60,
    )
    assert analytics["bucket"] == "adaptive"
    assert sum(point["count"] for point in analytics["mentions_over_time"]) == 2
