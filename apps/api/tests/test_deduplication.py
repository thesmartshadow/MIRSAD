from datetime import UTC, datetime

from mirsad_api.domains.clustering import cluster_items
from mirsad_api.domains.deduplication import (
    DeduplicationItem,
    canonicalize_url,
    cross_source_score,
    find_duplicate_groups,
)


def test_malformed_url_port_does_not_abort_canonicalization() -> None:
    assert canonicalize_url("https://example.com:not-a-port/story") == (
        "https://example.com/story"
    )


def item(key: int, source: str, url: str, text: str) -> DeduplicationItem:
    return DeduplicationItem(
        key=key,
        source=source,
        canonical_url=url,
        title="Shared story",
        text=text,
        published_at=datetime(2026, 1, key, tzinfo=UTC),
    )


def test_canonical_url_removes_tracking_and_fragment() -> None:
    assert canonicalize_url("HTTPS://Example.com/story/?utm_source=x&b=2&a=1#part") == (
        "https://example.com/story?a=1&b=2"
    )


def test_multi_stage_deduplication_preserves_all_members() -> None:
    items = [
        item(
            1,
            "rss",
            "https://example.com/story?utm_source=x",
            "A detailed shared report about public policy reform.",
        ),
        item(2, "gdelt", "https://example.com/story", "A different syndication excerpt."),
        item(
            3,
            "bluesky",
            "https://social.example/3",
            "A detailed shared report about public policy reform.",
        ),
        item(
            4,
            "github",
            "https://github.com/example/other",
            "Completely unrelated software project notes.",
        ),
    ]
    groups = find_duplicate_groups(items)
    assert len(groups) == 1
    assert set(groups[0].members) == {1, 2, 3}
    assert groups[0].stages[2] == "url"
    assert groups[0].stages[3] in {"fingerprint", "similarity"}
    assert groups[0].sources == ("bluesky", "gdelt", "rss")
    assert cross_source_score(3) == 60


def test_near_duplicate_grouping_does_not_create_transitive_false_merge() -> None:
    records = [
        item(1, "rss", "https://example.com/1", "one two three four five six seven eight nine ten"),
        item(
            2,
            "gdelt",
            "https://example.com/2",
            "two three four five six seven eight nine ten eleven",
        ),
        item(
            3,
            "x",
            "https://example.com/3",
            "three four five six seven eight nine ten eleven twelve",
        ),
    ]
    groups = find_duplicate_groups(records, similarity_threshold=0.78)
    assert len(groups) == 1
    assert set(groups[0].members) == {1, 2}


def test_story_clustering_is_stable_across_input_completion_order() -> None:
    records = [
        item(1, "rss", "https://example.com/a", "Baghdad summit public policy briefing"),
        item(2, "gdelt", "https://example.com/b", "Baghdad summit public policy analysis"),
        item(3, "github", "https://example.com/c", "Unrelated software release notes"),
    ]
    first = cluster_items(records)
    reversed_order = cluster_items(list(reversed(records)))
    assert [(cluster.members, cluster.representative_title) for cluster in first] == [
        (cluster.members, cluster.representative_title) for cluster in reversed_order
    ]


def test_story_clustering_keeps_canonical_url_duplicates_together() -> None:
    records = [
        item(1, "rss", "https://example.com/story?utm_source=rss", "Long original report"),
        item(2, "gdelt", "https://example.com/story", "Short wire excerpt"),
        item(3, "github", "https://example.com/other", "Unrelated software release"),
    ]

    clusters = cluster_items(records)

    assert any(set(cluster.members) == {1, 2} for cluster in clusters)


def test_story_clustering_merges_specific_event_without_merging_broad_topic() -> None:
    records = [
        DeduplicationItem(
            key=1,
            source="github",
            canonical_url="https://github.com/city/open-data",
            title="Open data portal",
            text="Municipal open data portal source repository.",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        DeduplicationItem(
            key=2,
            source="rss",
            canonical_url="https://city.example/open-data",
            title="Portal publishes open data",
            text="The city released datasets through its open data portal.",
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        DeduplicationItem(
            key=3,
            source="rss",
            canonical_url="https://markets.example/oil",
            title="Oil market outlook",
            text="Oil market prices and supply analysis.",
            published_at=datetime(2026, 1, 3, tzinfo=UTC),
        ),
        DeduplicationItem(
            key=4,
            source="rss",
            canonical_url="https://finance.example/iraq",
            title="Iraq investment outlook",
            text="Institutional analysis of Iraq investment conditions.",
            published_at=datetime(2026, 1, 4, tzinfo=UTC),
        ),
    ]

    clusters = cluster_items(records)

    assert any(set(cluster.members) == {1, 2} for cluster in clusters)
    assert not any({3, 4}.issubset(cluster.members) for cluster in clusters)
