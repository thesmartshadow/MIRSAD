from mirsad_api.quality import QUERY_JUDGMENTS, evaluate_search_quality


def test_search_quality_fixture_suite_is_reproducible() -> None:
    result = evaluate_search_quality()
    assert len(QUERY_JUDGMENTS) == 20
    assert result["fixture_records"] >= 25
    assert result["metrics"]["mean_reciprocal_rank"] >= 0.9
    assert result["metrics"]["mean_precision_at_5"] >= 0.2
    assert result["metrics"]["mean_returned_set_precision_at_5"] >= 0.9
    assert result["metrics"]["duplicate_records_detected"] >= 2
    assert result["metrics"]["exact_phrase_mean_precision_at_5"] >= 0.2
    assert result["metrics"]["exact_phrase_mean_returned_set_precision_at_5"] >= 0.9
    assert result["signal_checks"]["title_boost_relevance_delta"] > 0
    assert result["signal_checks"]["freshness_final_score_delta"] > 0
    assert result["signal_checks"]["engagement_final_score_delta"] > 0
    assert result["signal_checks"]["relevant_beats_high_engagement_collision"] is True


def test_exact_phrase_and_title_matching_behave_as_expected() -> None:
    result = evaluate_search_quality()
    cases = {case["query"]: case for case in result["cases"]}
    assert cases["Climate Policy"]["ranked"][0] in {"e01", "e02"}
    assert cases["وزارة الصحة"]["ranked"][0] == "a01"
    assert cases["MIRSAD العراق"]["ranked"][0] == "m01"
