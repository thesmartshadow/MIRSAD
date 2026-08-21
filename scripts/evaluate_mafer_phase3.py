from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from mirsad_api.domains.query import process_query
from mirsad_api.domains.retrieval_metrics import aggregate_metrics, ranking_metrics
from mirsad_api.mafer.assessment import (
    CandidateEvidence,
    UncertaintyLevel,
    assess_uncertainty,
)
from mirsad_api.mafer.calibration import (
    ObservableSearchEvidence,
    SaturationDecision,
    calibrated_uncertainty,
    saturation_decision,
)
from mirsad_api.mafer.intent import QueryIntentAnalyzer
from mirsad_api.mafer.versions import production_versions, shadow_versions

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "development": ROOT / "apps/api/tests/fixtures/mafer_phase3_development.json",
    "holdout": ROOT / "apps/api/tests/fixtures/mafer_phase3_holdout.json",
}
EXPECTED_HOLDOUT_SHA256 = "50b06e990e39e41995893b4de288553d16d4f575ca2d825554039004b23b5ca2"
CONFIG_PATH = ROOT / "reports/mafer-phase3-experimental-config.json"
FUSION_GRID = (0.25, 0.40, 0.55, 0.70)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ranked_from_round(case: dict[str, Any], round_data: dict[str, Any]) -> list[str]:
    count = max(20, int(round_data["candidate_count"]))
    relevant_ranks = set(int(value) for value in round_data["relevant_ranks"])
    relevant_index = 0
    irrelevant_index = 0
    ranked: list[str] = []
    for position in range(1, count + 1):
        if position in relevant_ranks:
            relevant_index += 1
            ranked.append(f"{case['id']}:relevant:{relevant_index}")
        else:
            irrelevant_index += 1
            ranked.append(f"{case['id']}:irrelevant:{irrelevant_index}")
    return ranked


def _round_metrics(case: dict[str, Any], round_data: dict[str, Any]) -> dict[str, Any]:
    relevant = {
        f"{case['id']}:relevant:{index}" for index in range(1, int(case["possible_relevant"]) + 1)
    }
    return ranking_metrics(_ranked_from_round(case, round_data), relevant)


def _production_evidence(round_data: dict[str, Any]) -> list[CandidateEvidence]:
    source_count = max(1, int(round_data["source_count"]))
    # Phase 2 treats any multi-variant support as a confidence reduction. The fixture's
    # agreement value controls whether that support is coherent only in the shadow model.
    variants = (
        ("original", "secondary") if round_data["variant_agreement"] < 0.95 else ("original",)
    )
    disagreement = float(round_data["lexical_semantic_disagreement"])
    return [
        CandidateEvidence(
            canonical_url=f"https://phase3.invalid/{index}",
            source=f"source-{index % source_count}",
            metadata_completeness=float(round_data["evidence_completeness"]),
            variant_ids=variants,
            engine_ids=("one-engine",) if round_data["single_engine"] else (),
            lexical_strength=max(0.0, 50 + disagreement / 2),
            semantic_strength=max(0.0, 50 - disagreement / 2),
        )
        for index in range(int(round_data["candidate_count"]))
    ]


def _observable(
    round_data: dict[str, Any], previous: dict[str, Any] | None
) -> ObservableSearchEvidence:
    return ObservableSearchEvidence(
        candidate_count=int(round_data["candidate_count"]),
        source_count=int(round_data["source_count"]),
        healthy_unqueried_sources=int(round_data["healthy_unqueried"]),
        variant_agreement=float(round_data["variant_agreement"]),
        lexical_semantic_disagreement=float(round_data["lexical_semantic_disagreement"]),
        rank_margin=float(round_data["rank_margin"]),
        evidence_completeness=float(round_data["evidence_completeness"]),
        single_engine_dependence=bool(round_data["single_engine"]),
        round_number=int(round_data["round"]),
        previous_unique_gain=int(previous["new_unique"]) if previous else None,
        current_unique_gain=int(round_data["new_unique"]),
        previous_admitted_gain=int(previous["new_admitted"]) if previous else None,
        current_admitted_gain=int(round_data["new_admitted"]),
    )


def _predict_stop(case: dict[str, Any], *, shadow: bool) -> tuple[int, list[dict[str, Any]]]:
    fingerprint = QueryIntentAnalyzer().analyze(
        process_query(case["query"], exact_phrase=case["class"] == "exact_phrase"),
        explicit_time_range=case["time_range"],
    )
    trace: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    cumulative_requests = 0
    for round_data in case["rounds"]:
        cumulative_requests += int(round_data["requests"])
        observable = _observable(round_data, previous)
        if shadow:
            uncertainty = calibrated_uncertainty(observable, fingerprint=fingerprint)
            decision = saturation_decision(
                observable,
                uncertainty,
                elapsed_seconds=float(round_data["latency_ms"]) / 1000,
                max_wall_clock_seconds=25,
                requests_used=cumulative_requests,
                max_requests=20,
                round_number=int(round_data["round"]),
                max_rounds=len(case["rounds"]),
            )
            should_stop = decision.decision == SaturationDecision.STOP
            trace.append(
                {
                    "round": round_data["round"],
                    "uncertainty": uncertainty.as_dict(),
                    "decision": decision.as_dict(),
                }
            )
        else:
            uncertainty = assess_uncertainty(
                _production_evidence(round_data),
                unqueried_useful_sources=int(round_data["healthy_unqueried"]),
            )
            safe_secondary_variants = {
                "EXACT",
                "ARABIC_NORMALIZED",
                "TRANSLITERATION",
                "ENTITY_ALIAS",
            }
            must_attempt_more = int(round_data["round"]) < len(case["rounds"]) and bool(
                safe_secondary_variants.intersection(case["useful_variants"])
            )
            # This is the Phase 2 SATISFIED condition used before marginal/source exhaustion.
            should_stop = (
                uncertainty.level == UncertaintyLevel.LOW
                and int(round_data["candidate_count"]) >= 10
                and not must_attempt_more
            ) or int(round_data["round"]) >= len(case["rounds"])
            trace.append(
                {
                    "round": round_data["round"],
                    "uncertainty": uncertainty.as_dict(),
                    "must_attempt_more": must_attempt_more,
                    "decision": "SATISFIED" if should_stop else "CONTINUE",
                }
            )
        if should_stop:
            return int(round_data["round"]), trace
        previous = round_data
    return len(case["rounds"]), trace


def _fusion_candidates(profile: str) -> list[dict[str, Any]]:
    profiles: dict[str, list[tuple[int, float, float, str, str]]] = {
        "identity": [
            (1, 98, 70, "github", "a"),
            (1, 91, 66, "rss", "b"),
            (1, 84, 63, "bluesky", "c"),
            (1, 78, 58, "youtube", "d"),
            (1, 70, 55, "reddit", "e"),
            (0, 18, 96, "youtube", "f"),
            (0, 28, 91, "rss", "g"),
            (0, 45, 84, "bluesky", "h"),
            (0, 58, 76, "github", "i"),
            (0, 64, 54, "reddit", "j"),
            (0, 40, 62, "mastodon", "k"),
            (0, 22, 82, "youtube", "l"),
        ],
        "exact": [
            (1, 100, 70, "rss", "a"),
            (1, 96, 67, "gdelt", "b"),
            (1, 90, 64, "youtube", "c"),
            (1, 85, 61, "reddit", "d"),
            (1, 78, 58, "github", "e"),
            (0, 35, 94, "youtube", "f"),
            (0, 48, 86, "rss", "g"),
            (0, 62, 77, "gdelt", "h"),
            (0, 68, 62, "github", "i"),
            (0, 52, 69, "reddit", "j"),
            (0, 40, 75, "bluesky", "k"),
            (0, 20, 88, "youtube", "l"),
        ],
        "topic": [
            (1, 66, 97, "rss", "a"),
            (1, 62, 93, "youtube", "b"),
            (1, 58, 90, "gdelt", "c"),
            (1, 55, 86, "reddit", "d"),
            (1, 52, 83, "bluesky", "e"),
            (1, 48, 80, "github", "f"),
            (0, 99, 35, "rss", "g"),
            (0, 92, 42, "github", "h"),
            (0, 84, 50, "youtube", "i"),
            (0, 75, 55, "reddit", "j"),
            (0, 65, 60, "mastodon", "k"),
            (0, 40, 68, "bluesky", "l"),
        ],
        "balanced": [
            (1, 92, 91, "rss", "a"),
            (1, 86, 88, "youtube", "b"),
            (1, 80, 84, "gdelt", "c"),
            (1, 74, 80, "reddit", "d"),
            (1, 68, 76, "bluesky", "e"),
            (0, 96, 52, "github", "f"),
            (0, 55, 89, "youtube", "g"),
            (0, 72, 65, "rss", "h"),
            (0, 60, 70, "reddit", "i"),
            (0, 48, 75, "mastodon", "j"),
            (0, 82, 48, "github", "k"),
            (0, 35, 78, "bluesky", "l"),
        ],
        "ambiguous": [
            (1, 95, 82, "rss", "a"),
            (1, 82, 90, "youtube", "b"),
            (1, 78, 86, "reddit", "c"),
            (1, 88, 72, "github", "d"),
            (1, 70, 80, "bluesky", "e"),
            (1, 65, 77, "mastodon", "f"),
            (0, 98, 48, "rss", "g"),
            (0, 52, 93, "youtube", "h"),
            (0, 85, 58, "github", "i"),
            (0, 45, 84, "reddit", "j"),
            (0, 76, 60, "bluesky", "k"),
            (0, 60, 69, "mastodon", "l"),
        ],
    }
    return [
        {
            "id": f"{profile}-{index}",
            "relevant": bool(relevant),
            "lexical": lexical,
            "semantic": semantic,
            "source": source,
            "story": story,
        }
        for index, (relevant, lexical, semantic, source, story) in enumerate(profiles[profile], 1)
    ]


def _fusion_ranking(profile: str, lexical_weight: float) -> tuple[list[str], set[str]]:
    candidates = _fusion_candidates(profile)
    ranked = sorted(
        candidates,
        key=lambda value: (
            lexical_weight * value["lexical"] + (1 - lexical_weight) * value["semantic"],
            value["lexical"],
            value["id"],
        ),
        reverse=True,
    )
    return [value["id"] for value in ranked], {
        value["id"] for value in candidates if value["relevant"]
    }


def _near_tie_diversity(
    ranked: list[dict[str, Any]], *, maximum_delta: float = 2.0
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    pending = list(ranked)
    while pending:
        best = pending.pop(0)
        if output:
            alternatives = [
                value
                for value in pending
                if best["score"] - value["score"] <= maximum_delta
                and value["story"] != output[-1]["story"]
                and value["source"] != output[-1]["source"]
            ]
            if alternatives:
                selected = alternatives[0]
                pending.remove(selected)
                pending.insert(0, best)
                best = selected
        output.append(best)
    return output


def _aggregate_cases(cases: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return aggregate_metrics(case[key] for case in cases)


def _stop_summary(cases: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    premature = [
        case for case in cases if case[f"{prefix}_stop_round"] < case["optimal_stop_after"]
    ]
    unnecessary = [
        case for case in cases if case[f"{prefix}_stop_round"] > case["optimal_stop_after"]
    ]
    false_gain = sum(
        int(case["rounds"][case["optimal_stop_after"] - 1]["admitted_relevant"])
        - int(case["rounds"][case[f"{prefix}_stop_round"] - 1]["admitted_relevant"])
        for case in premature
    )
    avoided = sum(
        sum(int(value["requests"]) for value in case["rounds"][case["optimal_stop_after"] :])
        for case in cases
        if case[f"{prefix}_stop_round"] == case["optimal_stop_after"]
    )
    return {
        "premature_stops": len(premature),
        "premature_stop_rate": round(len(premature) / len(cases), 4),
        "unnecessary_extra_rounds": len(unnecessary),
        "unnecessary_extra_round_rate": round(len(unnecessary) / len(cases), 4),
        "useful_admitted_gain_missed_after_false_stop": false_gain,
        "requests_avoided_by_correct_stopping": avoided,
        "premature_ids": [case["id"] for case in premature],
        "unnecessary_ids": [case["id"] for case in unnecessary],
    }


def _uncertainty_ordering(cases: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[case[f"{prefix}_uncertainty"]].append(case)
    return {
        level: {
            "queries": len(values),
            "candidate_recall": round(
                mean(value[f"{prefix}_candidate_recall"] for value in values), 4
            ),
            "p_at_5": round(mean(value[f"{prefix}_metrics"]["p_at_5"] for value in values), 4),
            "optimal_round": round(mean(value["optimal_stop_after"] for value in values), 3),
        }
        for level, values in sorted(grouped.items())
    }


def _bootstrap_delta(
    cases: list[dict[str, Any]], field: str, *, samples: int = 2000
) -> dict[str, float]:
    rng = random.Random(31032027)
    deltas: list[float] = []
    for _ in range(samples):
        sample = [cases[rng.randrange(len(cases))] for _ in cases]
        deltas.append(
            mean(float(value["shadow_metrics"][field]) for value in sample)
            - mean(float(value["production_metrics"][field]) for value in sample)
        )
    ordered = sorted(deltas)
    return {
        "mean": round(mean(deltas), 4),
        "lower_95": round(ordered[int(samples * 0.025)], 4),
        "upper_95": round(ordered[min(samples - 1, int(samples * 0.975))], 4),
    }


def _select_fusion_weights(cases: list[dict[str, Any]]) -> dict[str, float]:
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_class[case["class"]].append(case)
    selected: dict[str, float] = {}
    for query_class, values in sorted(by_class.items()):
        scored: list[tuple[float, float, float]] = []
        for weight in FUSION_GRID:
            metrics = []
            for case in values:
                ranked, relevant = _fusion_ranking(case["fusion_profile"], weight)
                metrics.append(ranking_metrics(ranked, relevant))
            aggregate = aggregate_metrics(metrics)
            scored.append((float(aggregate["ndcg_at_10"]), float(aggregate["p_at_5"]), weight))
        baseline = next(value for value in scored if value[2] == 0.25)
        best = max(scored, key=lambda value: (value[0], value[1], -abs(value[2] - 0.25)))
        selected[query_class] = (
            best[2] if best[0] >= baseline[0] + 0.02 and best[1] >= baseline[1] else 0.25
        )
    return selected


def evaluate(split: str) -> dict[str, Any]:
    path = FIXTURES[split]
    fixture_hash = _hash(path)
    if split == "holdout" and fixture_hash != EXPECTED_HOLDOUT_SHA256:
        raise RuntimeError("Frozen Phase 3 holdout hash does not match its recorded baseline")
    payload = _load(path)
    if split == "development":
        fusion_weights = _select_fusion_weights(payload["cases"])
    else:
        config = _load(CONFIG_PATH)
        if config["development_sha256"] != _hash(FIXTURES["development"]):
            raise RuntimeError("Experimental config is not tied to the current development set")
        if config["holdout_sha256"] != EXPECTED_HOLDOUT_SHA256:
            raise RuntimeError("Experimental config targets a different holdout")
        fusion_weights = {key: float(value) for key, value in config["fusion_weights"].items()}

    evaluated: list[dict[str, Any]] = []
    for case in payload["cases"]:
        production_round, production_trace = _predict_stop(case, shadow=False)
        shadow_round, shadow_trace = _predict_stop(case, shadow=True)
        production_data = case["rounds"][production_round - 1]
        shadow_data = case["rounds"][shadow_round - 1]
        production_metrics = _round_metrics(case, production_data)
        shadow_metrics = _round_metrics(case, shadow_data)
        production_uncertainty = production_trace[-1]["uncertainty"]["level"]
        shadow_uncertainty = shadow_trace[-1]["uncertainty"]["level"]
        lexical_weight = fusion_weights.get(case["class"], 0.25)
        production_fusion, fusion_relevant = _fusion_ranking(case["fusion_profile"], 0.25)
        shadow_fusion, _ = _fusion_ranking(case["fusion_profile"], lexical_weight)
        fusion_candidates = _fusion_candidates(case["fusion_profile"])
        scored_candidates = sorted(
            (
                {
                    **value,
                    "score": lexical_weight * value["lexical"]
                    + (1 - lexical_weight) * value["semantic"],
                }
                for value in fusion_candidates
            ),
            key=lambda value: (value["score"], value["lexical"], value["id"]),
            reverse=True,
        )
        diverse = _near_tie_diversity(scored_candidates)
        evaluated.append(
            {
                **case,
                "production_stop_round": production_round,
                "shadow_stop_round": shadow_round,
                "production_uncertainty": production_uncertainty,
                "shadow_uncertainty": shadow_uncertainty,
                "production_candidate_recall": round(
                    int(production_data["admitted_relevant"]) / int(case["possible_relevant"]), 4
                ),
                "shadow_candidate_recall": round(
                    int(shadow_data["admitted_relevant"]) / int(case["possible_relevant"]), 4
                ),
                "production_metrics": production_metrics,
                "shadow_metrics": shadow_metrics,
                "production_trace": production_trace,
                "shadow_trace": shadow_trace,
                "production_fusion_metrics": ranking_metrics(production_fusion, fusion_relevant),
                "shadow_fusion_metrics": ranking_metrics(shadow_fusion, fusion_relevant),
                "shadow_diversity_metrics": ranking_metrics(
                    [value["id"] for value in diverse], fusion_relevant
                ),
                "shadow_lexical_weight": lexical_weight,
                "arabic_loss_funnel": {
                    "possible_relevant": case["possible_relevant"],
                    "discovered": shadow_data["discovered_relevant"],
                    "canonical": shadow_data["canonical_relevant"],
                    "admitted": shadow_data["admitted_relevant"],
                    "semantic_evaluated": shadow_data["semantic_relevant"],
                    "top_10": sum(rank <= 10 for rank in shadow_data["relevant_ranks"]),
                }
                if case["language"] in {"arabic", "mixed"}
                else None,
            }
        )

    def segment(field: str, value: str, key: str) -> dict[str, Any]:
        return _aggregate_cases([case for case in evaluated if case[field] == value], key)

    languages = sorted({case["language"] for case in evaluated})
    classes = sorted({case["class"] for case in evaluated})
    result = {
        "schema": "mirsad.mafer-phase3-evaluation-result",
        "version": "1.0",
        "split": split,
        "fixture_sha256": fixture_hash,
        "queries": len(evaluated),
        "production_versions": production_versions(),
        "shadow_versions": shadow_versions(),
        "fusion_weights": fusion_weights,
        "production": {
            "retrieval_metrics": _aggregate_cases(evaluated, "production_metrics"),
            "candidate_recall": round(
                mean(case["production_candidate_recall"] for case in evaluated), 4
            ),
            "stop": _stop_summary(evaluated, "production"),
            "uncertainty_ordering": _uncertainty_ordering(evaluated, "production"),
            "fusion_metrics": _aggregate_cases(evaluated, "production_fusion_metrics"),
        },
        "shadow": {
            "retrieval_metrics": _aggregate_cases(evaluated, "shadow_metrics"),
            "candidate_recall": round(
                mean(case["shadow_candidate_recall"] for case in evaluated), 4
            ),
            "stop": _stop_summary(evaluated, "shadow"),
            "uncertainty_ordering": _uncertainty_ordering(evaluated, "shadow"),
            "fusion_metrics": _aggregate_cases(evaluated, "shadow_fusion_metrics"),
            "diversity_metrics": _aggregate_cases(evaluated, "shadow_diversity_metrics"),
        },
        "bootstrap_shadow_minus_production": {
            field: _bootstrap_delta(evaluated, field)
            for field in ("p_at_5", "p_at_10", "mrr", "recall_at_10", "ndcg_at_10")
        },
        "segments": {
            "language": {
                language: {
                    "production": segment("language", language, "production_metrics"),
                    "shadow": segment("language", language, "shadow_metrics"),
                    "production_candidate_recall": round(
                        mean(
                            case["production_candidate_recall"]
                            for case in evaluated
                            if case["language"] == language
                        ),
                        4,
                    ),
                    "shadow_candidate_recall": round(
                        mean(
                            case["shadow_candidate_recall"]
                            for case in evaluated
                            if case["language"] == language
                        ),
                        4,
                    ),
                }
                for language in languages
            },
            "class": {
                query_class: {
                    "production": segment("class", query_class, "production_metrics"),
                    "shadow": segment("class", query_class, "shadow_metrics"),
                }
                for query_class in classes
            },
        },
        "cases": evaluated,
    }
    report = ROOT / f"reports/mafer-phase3-{split}.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if split == "development":
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "schema": "mirsad.mafer-phase3-experimental-configuration",
                    "version": "1.0",
                    "status": "experimental_shadow",
                    "development_sha256": fixture_hash,
                    "holdout_sha256": EXPECTED_HOLDOUT_SHA256,
                    "fusion_weights": fusion_weights,
                    "uncertainty_version": shadow_versions()["uncertainty_version"],
                    "stop_model_version": shadow_versions()["stop_model_version"],
                    "reason": "Development-set calibration only; no production promotion",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=sorted(FIXTURES), required=True)
    args = parser.parse_args()
    result = evaluate(args.split)
    print(
        json.dumps(
            {
                "split": result["split"],
                "fixture_sha256": result["fixture_sha256"],
                "production": result["production"],
                "shadow": result["shadow"],
                "bootstrap": result["bootstrap_shadow_minus_production"],
                "segments": result["segments"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
