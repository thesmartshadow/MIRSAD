from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from statistics import mean

METRIC_FIELDS = (
    "p_at_5",
    "p_at_10",
    "mrr",
    "recall_at_10",
    "recall_at_20",
    "ndcg_at_5",
    "ndcg_at_10",
    "success_at_1",
    "success_at_3",
    "success_at_5",
)


def ranking_metrics(ranked: Sequence[str], relevant: set[str]) -> dict[str, object]:
    """Calculate binary-relevance IR metrics with a fixed Precision@K denominator."""

    if len(ranked) != len(set(ranked)):
        raise ValueError("Ranked identifiers must be unique")
    ranks = [index for index, identifier in enumerate(ranked, 1) if identifier in relevant]

    def precision(k: int) -> float:
        return len(set(ranked[:k]) & relevant) / k

    def recall(k: int) -> float:
        return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0

    def ndcg(k: int) -> float:
        actual = sum(1 / math.log2(index + 1) for index in ranks if index <= k)
        ideal = sum(1 / math.log2(index + 1) for index in range(1, min(k, len(relevant)) + 1))
        return actual / ideal if ideal else 0.0

    return {
        "p_at_5": round(precision(5), 4),
        "p_at_10": round(precision(10), 4),
        "mrr": round(1 / ranks[0], 4) if ranks else 0.0,
        "recall_at_10": round(recall(10), 4),
        "recall_at_20": round(recall(20), 4),
        "ndcg_at_5": round(ndcg(5), 4),
        "ndcg_at_10": round(ndcg(10), 4),
        "success_at_1": int(bool(ranks and ranks[0] <= 1)),
        "success_at_3": int(bool(ranks and ranks[0] <= 3)),
        "success_at_5": int(bool(ranks and ranks[0] <= 5)),
        "relevant_ranks": ranks,
    }


def aggregate_metrics(metrics: Iterable[dict[str, object]]) -> dict[str, float | int]:
    cases = list(metrics)
    return {
        "queries": len(cases),
        **{
            field: round(mean(float(case[field]) for case in cases), 4) if cases else 0.0
            for field in METRIC_FIELDS
        },
    }
