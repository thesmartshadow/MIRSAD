from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from itertools import combinations
from pathlib import Path

from mirsad_api.domains.clustering import (
    build_cluster_candidate_plan,
    cluster_items,
)
from mirsad_api.domains.deduplication import DeduplicationItem
from mirsad_api.domains.query import tokenize

FIXTURES = Path(__file__).parent / "fixtures"


def record(
    key: int,
    source: str,
    title: str | None,
    text: str,
    *,
    url: str | None = None,
    published_at: datetime | None = None,
) -> DeduplicationItem:
    return DeduplicationItem(
        key=key,
        source=source,
        canonical_url=url or f"https://{source}.example/{key}",
        title=title,
        text=text,
        published_at=published_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def memberships(clusters) -> set[frozenset[int]]:
    return {frozenset(cluster.members) for cluster in clusters}


def test_broad_query_phrase_alone_does_not_form_story_clusters() -> None:
    items = [
        record(
            1,
            "github",
            "kamranahammedaman/AiTooLBox",
            "Artificial Intelligence Tools Box",
        ),
        record(
            2,
            "github",
            "example/CSA1709-Artificial-intelligence",
            "example/CSA1709-Artificial-intelligence",
        ),
        record(
            3,
            "hacker_news",
            "The Artificial Intelligence Revolution (2015)",
            "The Artificial Intelligence Revolution (2015)",
        ),
        record(
            4,
            "github",
            "example/artificial-intelligence-and-black-chain-system",
            "example/artificial-intelligence-and-black-chain-system",
        ),
        record(
            5,
            "hacker_news",
            "Artificial Intelligence, Logic and Formalizing Common Sense",
            "Artificial Intelligence, Logic and Formalizing Common Sense by John McCarthy",
        ),
    ]

    plan = build_cluster_candidate_plan(
        items, query_tokens=tokenize("artificial intelligence")
    )
    clusters = cluster_items(
        items,
        query_tokens=tokenize("artificial intelligence"),
        candidate_plan=plan,
    )

    assert plan.pairs == ()
    assert all(len(cluster.members) == 1 for cluster in clusters)


def test_same_organization_different_events_remain_separate() -> None:
    items = [
        record(
            1,
            "rss",
            "OpenAI launches Orion model",
            "OpenAI unveiled Orion for multilingual public documents.",
        ),
        record(
            2,
            "gdelt",
            "OpenAI opens Baghdad office",
            "OpenAI announced a regional office and local hiring plan.",
        ),
        record(
            3,
            "rss",
            "OpenAI funds university grants",
            "OpenAI announced an independent research grant program.",
        ),
    ]

    clusters = cluster_items(items, query_tokens=tokenize("OpenAI"))

    assert all(len(cluster.members) == 1 for cluster in clusters)


def test_rewritten_cross_platform_story_clusters_with_explainable_evidence() -> None:
    items = [
        record(
            1,
            "gdelt",
            "Ministry launches Atlas satellite from Basra",
            "The communications ministry launched the Atlas satellite from Basra today.",
        ),
        record(
            2,
            "telegram",
            "Atlas spacecraft launched by ministry",
            "The Atlas satellite lifted off from Basra after the ministry announcement.",
            published_at=datetime(2026, 1, 1, 1, tzinfo=UTC),
        ),
        record(3, "github", "Atlas mapping library", "A map rendering software package."),
    ]
    plan = build_cluster_candidate_plan(items, query_tokens=tokenize("technology"))
    pair = (1, 2)
    clusters = cluster_items(
        items,
        query_tokens=tokenize("technology"),
        semantic_similarities={pair: 0.91},
        candidate_plan=plan,
    )

    story = next(cluster for cluster in clusters if set(cluster.members) == {1, 2})
    assert story.source_distribution == {"gdelt": 1, "telegram": 1}
    assert "semantic_similarity" in story.member_reasons[2]
    assert "shared_distinctive_terms" in story.member_reasons[2]


def test_duplicate_components_do_not_multiply_story_admission_evidence() -> None:
    items = [
        record(
            1,
            "rss",
            "Orion model launched",
            "OpenAI launched Orion for public document analysis.",
            url="https://news.example/orion?utm_source=rss",
        ),
        record(
            2,
            "gdelt",
            "Wire excerpt",
            "Short syndication excerpt.",
            url="https://news.example/orion",
        ),
        record(
            3,
            "youtube",
            "OpenAI Orion announcement explained",
            "Coverage of the Orion model launch for public document analysis.",
        ),
        record(
            4,
            "rss",
            "OpenAI opens a new office",
            "The company announced a local recruitment plan.",
        ),
    ]
    duplicate_groups = ((1, 2),)
    plan = build_cluster_candidate_plan(
        items,
        query_tokens=tokenize("OpenAI"),
        duplicate_groups=duplicate_groups,
    )
    semantic = {pair: 0.9 if 3 in pair else 0.4 for pair in plan.pairs}
    clusters = cluster_items(
        items,
        query_tokens=tokenize("OpenAI"),
        duplicate_groups=duplicate_groups,
        semantic_similarities=semantic,
        candidate_plan=plan,
    )

    story = next(cluster for cluster in clusters if {1, 2, 3}.issubset(cluster.members))
    assert set(story.members) == {1, 2, 3}
    assert story.member_reasons[2] == ("duplicate_component",)
    assert not any({1, 2, 4}.issubset(cluster.members) for cluster in clusters)


def test_arabic_and_mixed_language_same_story_clusters() -> None:
    items = [
        record(
            1,
            "rss",
            "إعادة افتتاح جسر الجمهورية في بغداد",
            "أعلنت أمانة بغداد إعادة افتتاح جسر الجمهورية بعد اكتمال الصيانة.",
        ),
        record(
            2,
            "telegram",
            None,
            "جسرُ الجمهورية يُفتتح مجدداً بعد انتهاء أعمال الصيانة في بغداد.",
            published_at=datetime(2026, 1, 1, 1, tzinfo=UTC),
        ),
        record(
            3,
            "gdelt",
            "Baghdad reopens Jumhuriya Bridge",
            "Baghdad Municipality reopened Jumhuriya Bridge after maintenance.",
            published_at=datetime(2026, 1, 1, 2, tzinfo=UTC),
        ),
        record(
            4,
            "rss",
            "وزارة الصحة تفتتح مستشفى في البصرة",
            "افتتاح مستشفى تخصصي جديد في محافظة البصرة.",
        ),
    ]
    query_tokens = tokenize("العراق بغداد")
    plan = build_cluster_candidate_plan(items, query_tokens=query_tokens)
    expected = {(1, 2), (1, 3), (2, 3)}
    semantic = {pair: 0.86 if pair in expected else 0.4 for pair in plan.pairs}
    clusters = cluster_items(
        items,
        query_tokens=query_tokens,
        semantic_similarities=semantic,
        candidate_plan=plan,
    )

    assert frozenset({1, 2, 3}) in memberships(clusters)
    assert not any(4 in cluster.members and len(cluster.members) > 1 for cluster in clusters)


def test_cluster_quality_fixture_has_no_false_or_missed_pairs_with_semantic_evidence() -> None:
    documents_payload = json.loads(
        (FIXTURES / "clustering_quality_documents.json").read_text(encoding="utf-8")
    )
    judgments = json.loads(
        (FIXTURES / "clustering_quality_judgments.json").read_text(encoding="utf-8")
    )
    documents = {document["id"]: document for document in documents_payload["documents"]}
    expected_total: set[tuple[str, str, str]] = set()
    predicted_total: set[tuple[str, str, str]] = set()

    for case in judgments["cases"]:
        key_by_id = {document_id: key for key, document_id in enumerate(case["document_ids"], 1)}
        id_by_key = {key: document_id for document_id, key in key_by_id.items()}
        items = [
            record(
                key_by_id[document_id],
                documents[document_id]["source"],
                documents[document_id]["title"],
                documents[document_id]["text"],
                url=documents[document_id]["url"],
                published_at=datetime.fromisoformat(
                    documents[document_id]["published_at"].replace("Z", "+00:00")
                ),
            )
            for document_id in case["document_ids"]
        ]
        expected = {
            tuple(sorted((left, right)))
            for group in case["same_story_groups"]
            for left, right in combinations(group, 2)
        }
        query_tokens = tokenize(case["query"])
        plan = build_cluster_candidate_plan(items, query_tokens=query_tokens)
        semantic = {
            pair: 0.86
            if tuple(sorted((id_by_key[pair[0]], id_by_key[pair[1]]))) in expected
            else 0.40
            for pair in plan.pairs
        }
        clusters = cluster_items(
            items,
            query_tokens=query_tokens,
            semantic_similarities=semantic,
            candidate_plan=plan,
        )
        expected_total.update((case["id"], *pair) for pair in expected)
        predicted_total.update(
            (case["id"], *tuple(sorted((id_by_key[left], id_by_key[right]))))
            for cluster in clusters
            for left, right in combinations(cluster.members, 2)
        )

    assert predicted_total - expected_total == set()
    assert expected_total - predicted_total == set()


def test_cluster_membership_is_stable_with_shuffled_input() -> None:
    items = [
        record(1, "rss", "Orion launch", "OpenAI launched Orion model in Baghdad."),
        record(2, "x", "OpenAI announcement", "Orion model launched in Baghdad."),
        record(3, "rss", "Different office event", "OpenAI opened an office in Baghdad."),
    ]
    query_tokens = tokenize("OpenAI Baghdad")
    plan = build_cluster_candidate_plan(items, query_tokens=query_tokens)
    semantic = {pair: 0.9 if pair == (1, 2) else 0.4 for pair in plan.pairs}

    first = cluster_items(
        items,
        query_tokens=query_tokens,
        semantic_similarities=semantic,
    )
    shuffled = cluster_items(
        [items[2], items[0], items[1]],
        query_tokens=query_tokens,
        semantic_similarities=semantic,
    )

    assert [(cluster.members, cluster.member_reasons) for cluster in first] == [
        (cluster.members, cluster.member_reasons) for cluster in shuffled
    ]


def test_large_heterogeneous_cluster_is_flagged_for_diagnostics() -> None:
    linked_items = [
        record(
            key,
            f"source-{key}",
            f"Atlas update {key}",
            "Distinct event context "
            + " ".join(
                f"link{min(key, other)}{max(key, other)}"
                for other in range(1, 6)
                if other != key
            ),
            published_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=key),
        )
        for key in range(1, 6)
    ]
    items = linked_items + [
        record(
            key,
            f"unrelated-{key}",
            f"Independent report {key}",
            f"Unrelated context unique{key}",
        )
        for key in range(6, 11)
    ]
    plan = build_cluster_candidate_plan(items)
    semantic = {pair: 0.80 for pair in plan.pairs}
    clusters = cluster_items(items, semantic_similarities=semantic, candidate_plan=plan)

    suspicious = next(cluster for cluster in clusters if len(cluster.members) == 5)
    assert suspicious.suspicious is True
    assert suspicious.suspicious_reason == "large_heterogeneous_cluster"


def test_candidate_blocking_remains_bounded_for_one_thousand_broad_results() -> None:
    items = [
        record(
            key,
            "fixture",
            f"Technology result unique{key}",
            f"A technology record about unique{key} with unrelated context.",
            published_at=None,
        )
        for key in range(1, 1001)
    ]

    plan = build_cluster_candidate_plan(items, query_tokens=tokenize("technology"))

    assert len(plan.pairs) <= len(items) * MAX_EXPECTED_PAIRS_PER_ITEM // 2
    assert plan.capped_pairs == 0


def test_repeated_story_templates_do_not_merge_distinct_event_identifiers() -> None:
    items = [
        record(
            story * 3 + variant + 1,
            ("rss", "telegram", "youtube")[variant],
            f"Ministry launches AtlasStory{story} satellite",
            f"The ministry launched AtlasStory{story} from Basra after an announcement.",
            published_at=datetime(2026, 1, 1, tzinfo=UTC)
            + timedelta(minutes=story * 3 + variant),
        )
        for story in range(10)
        for variant in range(3)
    ]
    plan = build_cluster_candidate_plan(items, query_tokens=tokenize("technology"))

    clusters = cluster_items(
        items,
        query_tokens=tokenize("technology"),
        semantic_similarities={pair: 0.95 for pair in plan.pairs},
        candidate_plan=plan,
    )

    assert {frozenset(cluster.members) for cluster in clusters} == {
        frozenset({story * 3 + 1, story * 3 + 2, story * 3 + 3})
        for story in range(10)
    }


MAX_EXPECTED_PAIRS_PER_ITEM = 24
