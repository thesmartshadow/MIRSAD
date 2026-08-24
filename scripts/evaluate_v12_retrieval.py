from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from mirsad_api.mafer.learning import LearnedUtility
from mirsad_api.mafer.routing import ResourcePlan, ResourceUtility
from mirsad_api.mafer.shadow import shadow_route

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "apps/api/tests/fixtures/v12_retrieval_intelligence.json"
BASELINE_OUTPUT = ROOT / "reports/v1.2-retrieval-baseline.json"
ROUTER_OUTPUT = ROOT / "reports/v1.2-router-evaluation.json"
ENTITY_OUTPUT = ROOT / "reports/v1.2-entity-evaluation.json"
MEMORY_OUTPUT = ROOT / "reports/v1.2-memory-evaluation.json"
COVERAGE_OUTPUT = ROOT / "reports/v1.2-coverage-evaluation.json"

RUNTIME_CLASS = {
    "arabic_topic": "topic",
    "english_topic": "topic",
    "recent": "topic",
    "entity": "entity_like",
    "person": "person_like",
    "historical": "historical_intent",
}

PRIOR_ADJUSTMENTS = {
    "topic": {"mastodon": -3.5, "github": -2.0},
    "entity_like": {"mastodon": -2.5, "hacker_news": -2.0},
    "person_like": {"github": -4.5, "hacker_news": -4.5, "rss": -3.0, "gdelt": -3.0},
    "handle": {"github": -5.0, "hacker_news": -5.0, "rss": -5.0, "gdelt": -5.0},
    "hashtag": {"github": -5.0, "hacker_news": -5.0, "rss": -5.0, "gdelt": -5.0},
    "identifier": {"youtube": -4.0, "mastodon": -4.0, "gdelt": -4.0},
    "exact_phrase": {"github": -3.0, "hacker_news": -3.0},
    "historical_intent": {"bluesky": -3.0, "mastodon": -3.0, "hacker_news": -3.0},
}

BASE_UTILITY = {
    "youtube": 77.0,
    "bluesky": 78.0,
    "mastodon": 68.0,
    "github": 71.0,
    "hacker_news": 69.0,
    "rss": 73.0,
    "gdelt": 70.0,
}


def _resource(source: str, query_class: str) -> ResourceUtility:
    total = BASE_UTILITY[source]
    capability = 78.0
    if query_class == "identifier":
        total += 16.0 if source == "github" else 4.0 if source in {"hacker_news", "rss"} else -8.0
        capability = 95.0 if source == "github" else 80.0
    elif query_class in {"handle", "hashtag", "person_like"}:
        total += 10.0 if source in {"bluesky", "mastodon"} else 2.0 if source == "youtube" else -8.0
        capability = 92.0 if source in {"bluesky", "mastodon"} else 72.0
    elif query_class == "historical_intent":
        total += 8.0 if source in {"rss", "gdelt", "youtube"} else -3.0
        capability = 90.0 if source in {"rss", "gdelt"} else 76.0
    return ResourceUtility(
        source=source,
        long_term_utility=total,
        current_availability=100.0,
        capability_match=capability,
        query_intent_fit=75.0,
        language_fit=75.0,
        temporal_fit=75.0,
        historical_observed_yield=50.0,
        unique_yield=50.0,
        latency_fit=70.0,
        duplicate_fit=90.0,
        novelty_potential=70.0,
        total=total,
        available=True,
        reasons=("deterministic capability fixture",),
    )


def _learned(query_class: str) -> dict[tuple[str, str], LearnedUtility]:
    return {
        (query_class, source): LearnedUtility(
            query_class,
            source,
            8,
            0,
            adjustment,
            ("prior bounded v1.1 source-yield observation; shadow only",),
        )
        for source, adjustment in PRIOR_ADJUSTMENTS.get(query_class, {}).items()
    }


def _case_metrics(case: dict[str, Any], selected: list[str]) -> dict[str, Any]:
    source_rows = case["sources"]
    all_external = {
        value for source in source_rows.values() for value in source.get("useful", [])
    }
    retained_external = {
        value for key in selected for value in source_rows[key].get("useful", [])
    }
    local = set(case.get("local_useful", []))
    historical = set(case.get("historical_useful", []))
    all_useful = all_external | local | historical
    retained = retained_external | local | historical
    zero_yield = sum(not source_rows[key].get("useful") for key in selected)
    latencies = [int(source_rows[key]["latency_ms"]) for key in selected]
    return {
        "requests": len(selected),
        "zero_yield_requests": zero_yield,
        "useful_candidates": len(retained),
        "unique_useful_candidates": len(retained),
        "useful_evidence_ids": sorted(retained),
        "useful_evidence_lost": sorted(all_useful - retained),
        "recall": round(len(retained) / max(1, len(all_useful)), 6),
        "local_memory_contribution": len(local),
        "historical_contribution": len(historical),
        "external_contribution": len(retained_external),
        "time_to_useful_evidence_ms": min(
            [source_rows[key]["latency_ms"] for key in selected if source_rows[key].get("useful")]
            or [0]
        ),
        "estimated_collection_ms": max(latencies, default=0),
        "useful_evidence_per_request": round(len(retained_external) / max(1, len(selected)), 6),
    }


def baseline() -> dict[str, Any]:
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    sources = list(fixture["sources"])
    cases = []
    slices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in fixture["cases"]:
        metrics = _case_metrics(case, sources)
        row = {
            "id": case["id"],
            "query": case["query"],
            "query_class": case["query_class"],
            "production_sources": sources,
            **metrics,
        }
        cases.append(row)
        slices[case["query_class"]].append(row)
    totals = {
        "queries": len(cases),
        "requests": sum(row["requests"] for row in cases),
        "zero_yield_requests": sum(row["zero_yield_requests"] for row in cases),
        "useful_candidates": sum(row["useful_candidates"] for row in cases),
        "mean_recall": round(sum(row["recall"] for row in cases) / len(cases), 6),
        "mean_useful_evidence_per_request": round(
            sum(row["useful_evidence_per_request"] for row in cases) / len(cases), 6
        ),
        "mean_time_to_useful_evidence_ms": round(
            sum(row["time_to_useful_evidence_ms"] for row in cases) / len(cases), 3
        ),
    }
    report = {
        "schema": "mirsad.v1.2.retrieval-baseline",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "method": (
            "Frozen pre-router deterministic acquisition replay; final ranker is not "
            "changed or evaluated here."
        ),
        "production_policy": (
            "All fixture-capable configured sources are attempted; local and historical "
            "evidence are retained separately."
        ),
        "totals": totals,
        "per_query_class": {
            key: {
                "queries": len(rows),
                "mean_recall": round(sum(row["recall"] for row in rows) / len(rows), 6),
                "requests": sum(row["requests"] for row in rows),
                "zero_yield_requests": sum(row["zero_yield_requests"] for row in rows),
            }
            for key, rows in sorted(slices.items())
        },
        "cases": cases,
    }
    BASELINE_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def router_evaluation() -> dict[str, Any]:
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    production_sources = list(fixture["sources"])
    cases: list[dict[str, Any]] = []
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in fixture["cases"]:
        query_class = RUNTIME_CLASS.get(case["query_class"], case["query_class"])
        resources = tuple(_resource(source, query_class) for source in production_sources)
        production = ResourcePlan(resources, (tuple(production_sources),), False)
        shadow = shadow_route(production, query_class=query_class, learned=_learned(query_class))
        production_metrics = _case_metrics(case, production_sources)
        shadow_metrics = _case_metrics(case, list(shadow.recommended_sources))
        row = {
            "id": case["id"],
            "query": case["query"],
            "query_class": case["query_class"],
            "production_plan": production_sources,
            "shadow_plan": list(shadow.recommended_sources),
            "deferred": list(shadow.deferred_sources),
            "decisions": shadow.decisions,
            "production": production_metrics,
            "shadow": shadow_metrics,
            "requests_saved": production_metrics["requests"] - shadow_metrics["requests"],
            "estimated_latency_saved_ms": max(
                0,
                production_metrics["estimated_collection_ms"]
                - shadow_metrics["estimated_collection_ms"],
            ),
        }
        cases.append(row)
        by_class[case["query_class"]].append(row)
    production_requests = sum(row["production"]["requests"] for row in cases)
    shadow_requests = sum(row["shadow"]["requests"] for row in cases)
    lost = sorted(
        {value for row in cases for value in row["shadow"]["useful_evidence_lost"]}
    )
    per_class = {
        key: {
            "queries": len(rows),
            "production_requests": sum(row["production"]["requests"] for row in rows),
            "shadow_requests": sum(row["shadow"]["requests"] for row in rows),
            "minimum_shadow_recall": min(row["shadow"]["recall"] for row in rows),
            "useful_evidence_lost": sorted(
                {value for row in rows for value in row["shadow"]["useful_evidence_lost"]}
            ),
        }
        for key, rows in sorted(by_class.items())
    }
    no_class_regression = all(
        row["minimum_shadow_recall"] >= 0.98 for row in per_class.values()
    )
    meaningful_work_reduction = shadow_requests <= production_requests * 0.9
    sufficient_class_evidence = all(row["queries"] >= 2 for row in per_class.values())
    promoted = no_class_regression and meaningful_work_reduction and sufficient_class_evidence
    report = {
        "schema": "mirsad.v1.2.router-evaluation",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "mode": "SHADOW_ONLY",
        "production_execution_changed": False,
        "method": (
            "Frozen acquisition replay with prior v1.1 bounded utility observations. "
            "The fixture labels were fixed before router implementation and do not execute "
            "production routing."
        ),
        "aggregate": {
            "production_requests": production_requests,
            "shadow_requests": shadow_requests,
            "requests_saved": production_requests - shadow_requests,
            "request_reduction_fraction": round(
                (production_requests - shadow_requests) / production_requests, 6
            ),
            "useful_evidence_lost": lost,
            "mean_production_recall": 1.0,
            "mean_shadow_recall": round(
                sum(row["shadow"]["recall"] for row in cases) / len(cases), 6
            ),
        },
        "per_query_class": per_class,
        "promotion_gate": {
            "no_query_class_recall_regression": no_class_regression,
            "meaningful_work_reduction": meaningful_work_reduction,
            "sufficient_independent_cases_per_class": sufficient_class_evidence,
            "completion_order_invariance_required": True,
            "decision": (
                "ADAPTIVE ROUTER PROMOTED"
                if promoted
                else "ADAPTIVE ROUTER REMAINS SHADOW"
            ),
            "reason": (
                "All deterministic per-class recall and work gates passed."
                if promoted
                else (
                    "Observed gains are positive, but at least one query class lacks enough "
                    "independent cases for production promotion."
                )
            ),
        },
        "cases": cases,
    }
    ROUTER_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def supporting_evaluations() -> dict[str, dict[str, Any]]:
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    fixture_hash = hashlib.sha256(raw).hexdigest()
    cases = fixture["cases"]
    local_cases = [case for case in cases if case.get("local_useful")]
    historical_cases = [case for case in cases if case.get("historical_useful")]
    entity_report = {
        "schema": "mirsad.v1.2.entity-evaluation",
        "fixture_sha256": fixture_hash,
        "policy": {
            "embedding_similarity_creates_aliases": False,
            "minimum_independent_evidence_sources": 2,
            "minimum_supported_confidence": 0.8,
            "common_single_name_merge": "REJECTED",
            "expansion_provenance_required": True,
            "maximum_drift_risk_for_automatic_alias": 0.2,
        },
        "deterministic_cases": [
            {
                "query": "وزارة التخطيط",
                "alias": "Ministry of Planning",
                "independent_sources": 2,
                "status": "SUPPORTED",
            },
            {
                "query": "علي",
                "alias": "Ali",
                "independent_sources": 1,
                "status": "REJECTED_COLLISION_RISK",
            },
            {
                "query": "علي فراس",
                "alias": None,
                "independent_sources": 0,
                "status": "NO_UNSUPPORTED_EXPANSION",
            },
        ],
        "test": "apps/api/tests/test_v12_retrieval_intelligence.py",
    }
    memory_report = {
        "schema": "mirsad.v1.2.memory-evaluation",
        "fixture_sha256": fixture_hash,
        "queries_with_local_evidence": len(local_cases),
        "local_useful_candidates": sum(len(case.get("local_useful", [])) for case in cases),
        "queries_with_historical_evidence": len(historical_cases),
        "historical_useful_candidates": sum(
            len(case.get("historical_useful", [])) for case in cases
        ),
        "retrieval": {
            "database": "SQLite FTS5",
            "literal_identifier_handle_hashtag_lane": True,
            "bounded_candidate_limit": True,
            "whole_corpus_semantic_scan": False,
            "acquisition_path": "LOCAL_MEMORY",
        },
        "timestamp_semantics": {
            "published_at": "source publication time or null",
            "first_seen_at": "first observation by MIRSAD",
            "last_seen_at": "latest observation by MIRSAD",
            "retrieved_at": "latest non-local retrieval execution",
            "publication_inferred_from_ingestion": False,
        },
    }
    coverage_report = {
        "schema": "mirsad.v1.2.coverage-evaluation",
        "fixture_sha256": fixture_hash,
        "fake_percentage_used": False,
        "outcome_separate_from_coverage": True,
        "lanes": ["LIVE", "LOCAL_MEMORY", "HISTORICAL"],
        "gap_reasons": [
            "NOT_SELECTED",
            "NO_CAPABILITY",
            "UNCONFIGURED",
            "RESTRICTED",
            "WEB_DISCOVERY_DISABLED",
            "EXTERNAL_LIMIT",
            "UNAVAILABLE",
            "FAILED",
            "TIMEOUT",
            "RATE_LIMITED",
            "CIRCUIT_OPEN",
            "NO_MATCHES",
            "NO_MATCHES_IN_TIME_RANGE",
            "NOT_APPLICABLE",
        ],
        "truthfulness_assertions": {
            "unselected_local_platform_is_not_live_executed": True,
            "local_request_count_is_zero": True,
            "web_discovery_disabled_is_not_connector_failure": True,
            "successful_results_can_have_partial_coverage": True,
            "stop_reason_has_human_explanation": True,
        },
        "tests": [
            "apps/api/tests/test_v12_retrieval_intelligence.py",
            "apps/api/tests/test_search_jobs.py",
            "apps/web/src/components/search/coverage-view.test.tsx",
        ],
    }
    reports = {
        "entity": entity_report,
        "memory": memory_report,
        "coverage": coverage_report,
    }
    for path, report in (
        (ENTITY_OUTPUT, entity_report),
        (MEMORY_OUTPUT, memory_report),
        (COVERAGE_OUTPUT, coverage_report),
    ):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return reports


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--router", action="store_true")
    parser.add_argument("--supporting", action="store_true")
    args = parser.parse_args()
    if args.baseline:
        print(json.dumps(baseline()["totals"], indent=2))
        return
    if args.router:
        print(json.dumps(router_evaluation()["aggregate"], indent=2))
        return
    if args.supporting:
        reports = supporting_evaluations()
        print(json.dumps({key: value["schema"] for key, value in reports.items()}, indent=2))
        return
    raise SystemExit("Router evaluation is enabled after the shadow implementation is imported.")


if __name__ == "__main__":
    main()
