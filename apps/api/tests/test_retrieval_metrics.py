import pytest

from mirsad_api.domains.retrieval_metrics import aggregate_metrics, ranking_metrics


def test_metrics_use_fixed_k_denominators_and_first_hit_mrr() -> None:
    metrics = ranking_metrics(["relevant", "n1", "n2"], {"relevant"})

    assert metrics["p_at_5"] == 0.2
    assert metrics["p_at_10"] == 0.1
    assert metrics["mrr"] == 1.0
    assert metrics["recall_at_10"] == 1.0
    assert metrics["ndcg_at_5"] == 1.0
    assert metrics["success_at_1"] == 1


def test_metrics_reproduce_known_multi_relevant_ranking() -> None:
    metrics = ranking_metrics(["n1", "r1", "n2", "r2", "n3", "r3"], {"r1", "r2", "r3"})

    assert metrics["p_at_5"] == 0.4
    assert metrics["mrr"] == 0.5
    assert metrics["recall_at_10"] == 1.0
    assert metrics["success_at_1"] == 0
    assert metrics["success_at_3"] == 1
    assert metrics["relevant_ranks"] == [2, 4, 6]
    assert metrics["ndcg_at_5"] == pytest.approx(0.4982, abs=0.0001)


def test_metrics_reject_duplicate_ranked_identifiers() -> None:
    with pytest.raises(ValueError, match="unique"):
        ranking_metrics(["same", "same"], {"same"})


def test_metric_aggregation_is_macro_average() -> None:
    first = ranking_metrics(["r", "n"], {"r"})
    second = ranking_metrics(["n", "r"], {"r"})

    aggregate = aggregate_metrics([first, second])

    assert aggregate["queries"] == 2
    assert aggregate["mrr"] == 0.75
    assert aggregate["success_at_1"] == 0.5
