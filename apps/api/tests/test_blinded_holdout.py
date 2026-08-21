from scripts.evaluate_blinded_holdout import evaluate_holdout


def test_blinded_holdout_is_dense_separate_and_uses_unchanged_ranking() -> None:
    result = evaluate_holdout()

    assert result["algorithm_changed_for_holdout"] is False
    assert result["documents"] >= 90
    assert result["queries"] >= 15
    assert result["minimum_candidates_per_query"] >= 10
    assert all(case["candidate_count"] >= 10 for case in result["cases"])
    assert result["fixture_relations"]["near_duplicates"]
    assert result["fixture_relations"]["same_story_different_content"]


def test_blinded_holdout_reports_required_language_and_difficulty_slices() -> None:
    result = evaluate_holdout()

    assert set(result["language_metrics"]) == {"arabic", "english", "mixed"}
    assert {"exact_phrase", "ambiguous", "hard"}.issubset(result["slice_metrics"])
    for metrics in (*result["language_metrics"].values(), *result["slice_metrics"].values()):
        assert 0 <= metrics["p_at_5"] <= 1
        assert 0 <= metrics["p_at_10"] <= 1
        assert 0 <= metrics["mrr"] <= 1


def test_blinded_holdout_exercises_nonconstant_score_components() -> None:
    statistics = evaluate_holdout()["component_statistics"]

    for component in (
        "relevance",
        "freshness",
        "engagement",
        "source_confidence",
        "cross_source_presence",
        "novelty",
        "final_score",
    ):
        assert statistics[component]["stddev"] > 0
