from mirsad_api.domains.engagement import normalize_engagement


def test_platform_engagement_is_scaled_per_adapter() -> None:
    hn = normalize_engagement("hacker_news", {"points": 45, "comments": 35})
    youtube = normalize_engagement("youtube", {"views": 45, "likes": 35, "comments": 0})
    assert hn == 100
    assert youtube < 30


def test_engagement_is_bounded_and_unknown_sources_are_neutral() -> None:
    github = normalize_engagement(
        "github", {"stars": 10_000_000, "forks": 10_000, "comments": 10_000}
    )
    assert github == 100
    assert normalize_engagement("rss", {}) == 0
    assert normalize_engagement("unknown", {"likes": 1000}) == 0


def test_boolean_or_missing_values_are_not_reported_as_engagement() -> None:
    assert normalize_engagement("gdelt", {"mentions": True}) == 0
    assert normalize_engagement("youtube", {"views": None}) == 0
