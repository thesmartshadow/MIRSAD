from datetime import UTC, datetime, timedelta

import pytest

from mirsad_api.domains.query import process_query
from mirsad_api.domains.ranking import (
    calculate_score,
    freshness_score,
    is_candidate_match,
    relevance_score,
)

WEIGHTS = {
    "relevance": 0.35,
    "freshness": 0.20,
    "engagement": 0.15,
    "source_confidence": 0.10,
    "cross_source_presence": 0.10,
    "novelty": 0.10,
}


def test_freshness_uses_exponential_half_life() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert freshness_score(now, now=now, half_life_hours=48) == 100
    assert freshness_score(now - timedelta(hours=48), now=now, half_life_hours=48) == 50
    assert freshness_score(now - timedelta(hours=96), now=now, half_life_hours=48) == 25


def test_explainable_score_matches_weighted_formula() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    score = calculate_score(
        query=process_query("public policy", exact_phrase=True),
        title="Public policy briefing",
        text="A detailed public policy briefing with enough text to avoid a short-content penalty.",
        canonical_url="https://example.com/report",
        published_at=now,
        engagement=50,
        source_confidence=80,
        cross_source_presence=40,
        novelty=100,
        bm25_normalized=100,
        weights=WEIGHTS,
        now=now,
    )
    assert score.relevance == 100
    assert score.freshness == 100
    assert score.final_score == 84.5
    assert score.matched_terms == ("public", "policy")


def test_scoring_rejects_invalid_weight_total() -> None:
    with pytest.raises(ValueError, match="total 1.0"):
        calculate_score(
            query=process_query("test"),
            title="test",
            text="test content long enough for deterministic ranking validation",
            canonical_url="https://example.com/test",
            published_at=None,
            engagement=0,
            source_confidence=50,
            weights={**WEIGHTS, "relevance": 0.5},
        )


def test_phrase_and_hashtag_intent_do_not_degrade_to_substring_matching() -> None:
    phrase = process_query('"open data portal"')
    assert is_candidate_match(phrase, "Open data portal", "Public datasets")
    assert not is_candidate_match(phrase, "Open portal", "Data appears elsewhere")
    hashtag = process_query("#بغداد")
    assert is_candidate_match(hashtag, None, "خبر #بغداد العام")
    assert not is_candidate_match(hashtag, "مؤتمر بغداد", "خبر عام")


def test_token_proximity_and_title_phrase_are_bounded_relevance_signals() -> None:
    query = process_query("open data")
    near, _ = relevance_score(query, None, "An open data release", bm25_normalized=50)
    far, _ = relevance_score(
        query,
        None,
        "Open publication with several unrelated institutional words before data appears",
        bm25_normalized=50,
    )
    title, _ = relevance_score(query, "Open data bulletin", "Details", bm25_normalized=50)
    assert title > near > far


def test_supporting_signals_cannot_rescue_weak_relevance() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    weak = calculate_score(
        query=process_query("public policy institutional framework"),
        title="Public entertainment",
        text="Popular content with no relevant institutional context at all.",
        canonical_url="https://example.com/popular",
        published_at=now,
        engagement=100,
        source_confidence=100,
        cross_source_presence=100,
        novelty=100,
        bm25_normalized=25,
        weights=WEIGHTS,
        now=now,
    )
    strong = calculate_score(
        query=process_query("public policy institutional framework"),
        title="Institutional framework",
        text="A complete public policy institutional framework with detailed analysis.",
        canonical_url="https://example.com/relevant",
        published_at=now - timedelta(days=30),
        engagement=0,
        source_confidence=50,
        cross_source_presence=0,
        novelty=50,
        bm25_normalized=100,
        weights=WEIGHTS,
        now=now,
    )
    assert strong.final_score > weak.final_score


def test_semantic_secondary_quality_is_bounded_by_relevance() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    weak = calculate_score(
        query=process_query("climate adaptation policy"),
        title="Climate promotion",
        text="A viral entertainment promotion with an incidental climate mention.",
        canonical_url="https://example.com/viral",
        published_at=now,
        engagement=100,
        source_confidence=100,
        cross_source_presence=100,
        novelty=100,
        bm25_normalized=20,
        semantic_relevance=25,
        weights=WEIGHTS,
        now=now,
    )
    strong = calculate_score(
        query=process_query("climate adaptation policy"),
        title="Climate adaptation policy review",
        text="A detailed older assessment of national resilience policy.",
        canonical_url="https://example.com/substantive",
        published_at=now - timedelta(days=30),
        engagement=0,
        source_confidence=50,
        semantic_relevance=80,
        weights=WEIGHTS,
        now=now,
    )

    assert strong.final_score > weak.final_score
    assert strong.secondary_quality_budget == 0.01
    assert strong.ranking_strategy == "lexical_candidate_semantic_rerank"


def test_strong_exact_phrase_evidence_beats_weak_semantic_similarity() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    query = process_query('"National Cyber Center"')
    strong = calculate_score(
        query=query,
        title="National Cyber Center incident review",
        text="The center published a technical incident review with response actions.",
        canonical_url="https://example.com/review",
        published_at=now,
        engagement=0,
        source_confidence=60,
        bm25_normalized=100,
        semantic_relevance=55,
        weights=WEIGHTS,
        now=now,
    )
    weak = calculate_score(
        query=query,
        title="Retail center promotion",
        text="A promotion mentions National Cyber Center as an unrelated campaign phrase.",
        canonical_url="https://example.com/promotion",
        published_at=now,
        engagement=100,
        source_confidence=100,
        bm25_normalized=25,
        semantic_relevance=35,
        weights=WEIGHTS,
        now=now,
    )

    assert strong.final_score > weak.final_score
    assert strong.relevance_features["title_exact_phrase"] == 100
