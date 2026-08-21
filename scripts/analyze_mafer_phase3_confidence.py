from __future__ import annotations

import json
import random
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "reports/mafer-phase3-holdout.json"
MINILM = ROOT / "reports/mafer-phase3-model-minilm-holdout.json"
MPNET = ROOT / "reports/mafer-phase3-model-mpnet-holdout.json"
OUTPUT = ROOT / "reports/mafer-phase3-confidence.json"
EXPECTED_HOLDOUT_SHA256 = "50b06e990e39e41995893b4de288553d16d4f575ca2d825554039004b23b5ca2"


def paired_interval(
    pairs: list[tuple[float, float]], *, samples: int = 10_000, seed: int = 20260810
) -> dict[str, float]:
    observed = mean(shadow - production for production, shadow in pairs)
    randomizer = random.Random(seed)
    deltas = sorted(
        mean(
            pairs[index][1] - pairs[index][0]
            for index in (randomizer.randrange(len(pairs)) for _ in pairs)
        )
        for _ in range(samples)
    )
    return {
        "mean": round(observed, 4),
        "lower_95": round(deltas[int(samples * 0.025)], 4),
        "upper_95": round(deltas[int(samples * 0.975)], 4),
    }


def compare_case_metrics(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    left_field: str,
    right_field: str,
) -> dict[str, dict[str, float]]:
    right_by_id = {case["id"]: case for case in right}
    metrics = ("p_at_5", "p_at_10", "mrr", "recall_at_10", "ndcg_at_10")
    return {
        metric: paired_interval(
            [
                (
                    float(case[left_field][metric]),
                    float(right_by_id[case["id"]][right_field][metric]),
                )
                for case in left
            ]
        )
        for metric in metrics
    }


def main() -> None:
    holdout = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    if holdout["fixture_sha256"] != EXPECTED_HOLDOUT_SHA256:
        raise RuntimeError("Frozen Phase-3 holdout hash mismatch")
    minilm = json.loads(MINILM.read_text(encoding="utf-8"))
    mpnet = json.loads(MPNET.read_text(encoding="utf-8"))
    result = {
        "schema": "mirsad.mafer-phase3-paired-confidence",
        "version": "1.0",
        "holdout_sha256": EXPECTED_HOLDOUT_SHA256,
        "bootstrap_samples": 10_000,
        "seed": 20260810,
        "query_aware_fusion_minus_production": compare_case_metrics(
            holdout["cases"],
            holdout["cases"],
            "production_fusion_metrics",
            "shadow_fusion_metrics",
        ),
        "near_tie_diversity_minus_query_aware_fusion": compare_case_metrics(
            holdout["cases"],
            holdout["cases"],
            "shadow_fusion_metrics",
            "shadow_diversity_metrics",
        ),
        "mpnet_minus_minilm": compare_case_metrics(
            minilm["cases"], mpnet["cases"], "metrics", "metrics"
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
