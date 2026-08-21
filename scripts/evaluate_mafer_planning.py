from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Literal, cast

from mirsad_api.connectors import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorItem,
    ConnectorMetadata,
)
from mirsad_api.domains.query import process_query
from mirsad_api.domains.retrieval_metrics import aggregate_metrics, ranking_metrics
from mirsad_api.mafer.assessment import CandidateEvidence, assess_uncertainty
from mirsad_api.mafer.budget import SearchMode, budget_for
from mirsad_api.mafer.fusion import (
    DiscoveryRankObservation,
    weighted_reciprocal_rank_fusion,
)
from mirsad_api.mafer.intent import QueryIntentAnalyzer
from mirsad_api.mafer.lattice import QueryVariant, QueryVariantType, build_query_lattice
from mirsad_api.mafer.routing import ResourceRouter

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "apps/api/tests/fixtures/mafer_planning_benchmark.json"
JSON_REPORT = ROOT / "reports/mafer-phase2-benchmark.json"
Category = Literal["social", "news", "developer_community"]


class BenchmarkConnector(BaseConnector):
    def __init__(
        self,
        key: str,
        category: Category,
        capabilities: ConnectorCapabilities,
        latency_ms: float,
    ) -> None:
        self.metadata = ConnectorMetadata(
            key=key,
            name=key,
            kind="benchmark",
            base_url=f"https://{key}.benchmark.invalid",
            category=category,
            capabilities=capabilities,
        )
        super().__init__()
        self.latency_ms = latency_ms

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def search(self, query: str, *, limit: int, since=None) -> list[ConnectorItem]:
        raise RuntimeError("planning benchmark does not execute network connectors")

    def normalize(self, payload):
        raise NotImplementedError


def connectors() -> dict[str, BenchmarkConnector]:
    common = dict(
        keyword_search=True,
        phrase_search=True,
        recent_search=True,
        full_text_search=True,
    )
    definitions = {
        "bluesky": (
            "social",
            ConnectorCapabilities(
                **common,
                hashtag_search=True,
                author_search=True,
                language_filter=True,
            ),
            420,
        ),
        "x": (
            "social",
            ConnectorCapabilities(
                **common,
                hashtag_search=True,
                author_search="conditional",
                web_index_search=True,
                historical_search="conditional",
                acquisition_modes=("WEB_INDEX",),
            ),
            1200,
        ),
        "threads": (
            "social",
            ConnectorCapabilities(
                **common,
                hashtag_search=True,
                web_index_search=True,
                acquisition_modes=("WEB_INDEX",),
            ),
            1250,
        ),
        "reddit": (
            "social",
            ConnectorCapabilities(
                **common,
                author_search="conditional",
                web_index_search=True,
                historical_search=True,
                acquisition_modes=("WEB_INDEX",),
            ),
            1100,
        ),
        "youtube": (
            "social",
            ConnectorCapabilities(
                **common,
                hashtag_search=True,
                author_search="conditional",
                language_filter=True,
                historical_search=True,
            ),
            650,
        ),
        "mastodon": (
            "social",
            ConnectorCapabilities(
                keyword_search="conditional",
                phrase_search="conditional",
                hashtag_search=True,
                author_search="conditional",
                recent_search=True,
                public_timeline=True,
            ),
            500,
        ),
        "github": (
            "developer_community",
            ConnectorCapabilities(
                **common,
                author_search=True,
                identifier_search=True,
                historical_search=True,
            ),
            520,
        ),
        "hacker_news": (
            "developer_community",
            ConnectorCapabilities(
                **common,
                author_search=True,
                identifier_search="conditional",
                historical_search=True,
            ),
            310,
        ),
        "rss": (
            "news",
            ConnectorCapabilities(
                **common,
                identifier_search="conditional",
                historical_search="conditional",
            ),
            700,
        ),
        "gdelt": (
            "news",
            ConnectorCapabilities(
                **common,
                language_filter=True,
                identifier_search="conditional",
                historical_search=True,
            ),
            3000,
        ),
    }
    return {
        key: BenchmarkConnector(
            key,
            cast(Category, category),
            capabilities,
            latency,
        )
        for key, (category, capabilities, latency) in definitions.items()
    }


@dataclass(frozen=True, slots=True)
class Strategy:
    name: str
    intent_routing: bool = False
    lattice: bool = False
    memory: bool = False
    weighted_rrf: bool = False
    multi_round: bool = False
    uncertainty: bool = False
    expansion: bool = False


STRATEGIES = (
    Strategy("BASELINE"),
    Strategy("+ Intent routing", intent_routing=True),
    Strategy("+ Query lattice", intent_routing=True, lattice=True),
    Strategy("+ Local memory round 0", True, True, True),
    Strategy("+ Weighted RRF", True, True, True, True),
    Strategy("+ Uncertainty", True, True, True, True, False, True),
    Strategy("+ Multi-round escalation", True, True, True, True, True, True),
    Strategy("+ Gated evidence expansion", True, True, True, True, True, True, True),
)


def _hash_url(*parts: str) -> str:
    value = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:20]
    return f"https://planning.benchmark.invalid/{value}"


def _supports(connector: BenchmarkConnector, variant: QueryVariant) -> bool:
    if variant.transformation == QueryVariantType.ORIGINAL:
        return connector.metadata.capabilities.keyword_search is not False
    capabilities = connector.metadata.capabilities.as_dict()
    return any(capabilities.get(name) is not False for name in variant.eligible_source_capabilities)


def _is_useful(query: dict[str, Any], source: str, variant: QueryVariant) -> bool:
    if source not in query["useful_sources"]:
        return False
    requirements = query.get("variant_requirements", {}).get(source)
    allowed = requirements or query["useful_variants"]
    return variant.transformation.value in allowed


def _secondary(variants: tuple[QueryVariant, ...], round_number: int) -> list[QueryVariant]:
    if round_number == 2:
        allowed = {
            QueryVariantType.EXACT,
            QueryVariantType.ARABIC_NORMALIZED,
            QueryVariantType.TRANSLITERATION,
            QueryVariantType.ENTITY_ALIAS,
        }
        return [
            value
            for value in variants
            if value.transformation in allowed and value.text != variants[0].text
        ]
    return [
        value
        for value in variants
        if value.transformation == QueryVariantType.EVIDENCE_EXPANDED
        and value.round_created == round_number
    ]


def _action_url(query: dict[str, Any], source: str, variant: QueryVariant) -> tuple[str, bool]:
    useful = _is_useful(query, source, variant)
    return (
        _hash_url(query["id"], source, "useful")
        if useful
        else _hash_url(query["id"], source, variant.transformation.value, "collision"),
        useful,
    )


def evaluate_case(query: dict[str, Any], strategy: Strategy, mode: SearchMode) -> dict[str, Any]:
    available = connectors()
    budget = budget_for(mode)
    processed = process_query(
        query["query"],
        exact_phrase=query["class"] == "exact_phrase",
    )
    fingerprint = QueryIntentAnalyzer().analyze(
        processed,
        explicit_time_range=query["time_range"],
    )
    lattice = build_query_lattice(
        processed,
        fingerprint,
        max_variants=budget.max_query_variants if strategy.lattice else 1,
    )
    if strategy.intent_routing:
        plan = ResourceRouter().route(
            fingerprint,
            available,
            available,
            budget,
            explicit_selection=False,
            current_states={source: "healthy" for source in available},
        )
        source_rounds = list(plan.rounds)
        utility = {item.source: item.total / 100 for item in plan.ordered}
    else:
        source_rounds = [tuple(sorted(available))]
        utility = {source: 1.0 for source in available}
    if not strategy.multi_round:
        source_rounds = [tuple(source for values in source_rounds for source in values)]

    actions: list[tuple[str, QueryVariant, int]] = []
    queried: set[str] = set()
    stop_reason = "SOURCE_EXHAUSTION"
    max_rounds = budget.max_rounds if strategy.multi_round else 1
    for round_number, round_sources in enumerate(source_rounds[:max_rounds], 1):
        for source in round_sources:
            source_calls = {(value[0], value[2]) for value in actions}
            if len(source_calls) >= budget.max_source_calls:
                stop_reason = "REQUEST_BUDGET"
                break
            actions.append((source, lattice.original, round_number))
            queried.add(source)
            if strategy.lattice and available[source].active_acquisition_mode() == "WEB_INDEX":
                actions.extend(
                    (source, variant, round_number)
                    for variant in lattice.variants
                    if variant is not lattice.original
                    and variant.round_created <= round_number
                    and _supports(available[source], variant)
                )
        if strategy.multi_round and round_number > 1:
            for source in [item for values in source_rounds[: round_number - 1] for item in values]:
                for variant in _secondary(lattice.variants, round_number):
                    if _supports(available[source], variant):
                        actions.append((source, variant, round_number))
                        break
        if strategy.uncertainty:
            evidence = [
                CandidateEvidence(
                    canonical_url=_action_url(query, source, variant)[0],
                    source=source,
                    metadata_completeness=0.7,
                    variant_ids=(variant.variant_id,),
                    engine_ids=(source,)
                    if available[source].active_acquisition_mode() == "WEB_INDEX"
                    else (),
                )
                for source, variant, _action_round in actions
            ]
            uncertainty = assess_uncertainty(
                evidence,
                unqueried_useful_sources=sum(
                    len(values) for values in source_rounds[round_number:]
                ),
            )
            pending_safe_variant = bool(
                round_number < max_rounds and _secondary(lattice.variants, round_number + 1)
            )
            if (
                uncertainty.level.value == "LOW"
                and len({item.canonical_url for item in evidence}) >= 10
                and not pending_safe_variant
            ):
                stop_reason = "SATISFIED"
                break
        if stop_reason == "REQUEST_BUDGET":
            break
        stop_reason = "MAX_ROUNDS" if round_number >= max_rounds else "CONTINUE"

    observations: list[DiscoveryRankObservation] = []
    first_seen: list[str] = []
    relevant: set[str] = set()
    action_evidence: list[CandidateEvidence] = []
    if strategy.memory:
        for index in range(int(query.get("memory", 0))):
            url = _hash_url(query["id"], "memory", str(index))
            relevant.add(url)
            first_seen.append(url)
            observations.append(
                DiscoveryRankObservation(url, "local_memory", "memory", index + 1, 1.1)
            )
    for source, variant, round_number in actions:
        url, useful = _action_url(query, source, variant)
        if useful:
            relevant.add(url)
        if url not in first_seen:
            first_seen.append(url)
        action_evidence.append(CandidateEvidence(url, source, 0.7))
        observations.append(
            DiscoveryRankObservation(
                url,
                source,
                variant.variant_id,
                1,
                engine_weight=utility.get(source, 1.0),
                variant_confidence=variant.confidence,
                round_number=round_number,
            )
        )

    if strategy.weighted_rrf:
        ranked = [value.canonical_url for value in weighted_reciprocal_rank_fusion(observations)]
    else:
        ranked = first_seen
    # Fixed denominators remain meaningful because every case has at least ten
    # judged source outcomes, including difficult collisions.
    zero_result = not bool(ranked)
    while len(ranked) < 10:
        ranked.append(_hash_url(query["id"], "padding", str(len(ranked))))
    all_relevant = {_hash_url(query["id"], source, "useful") for source in query["useful_sources"]}
    all_relevant.update(
        _hash_url(query["id"], "memory", str(index))
        for index in range(int(query.get("memory", 0)))
        if strategy.memory
    )
    metrics = ranking_metrics(ranked, all_relevant)
    uncertainty = assess_uncertainty(action_evidence)
    unique_sources = {source for source, _variant, _round in actions}
    source_calls = {(source, round_number) for source, _variant, round_number in actions}
    round_latencies = []
    for round_number in sorted({value[2] for value in actions}):
        values = {
            source for source, _variant, action_round in actions if action_round == round_number
        }
        round_latencies.append(max((available[source].latency_ms for source in values), default=0))
    return {
        "id": query["id"],
        "language": query["language"],
        "class": query["class"],
        "metrics": metrics,
        "relevant_candidate_yield": len(relevant),
        "possible_relevant_urls": len(all_relevant),
        "candidate_recall": round(len(relevant) / len(all_relevant), 4) if all_relevant else 0,
        "unique_useful_urls": len(relevant),
        "requests": len(source_calls),
        "sources": len(unique_sources),
        "variant_attempts": len(actions),
        "rounds": max((value[2] for value in actions), default=0),
        "simulated_external_latency_ms": sum(round_latencies),
        "uncertainty": uncertainty.level.value,
        "stop_reason": stop_reason,
        "zero_result": zero_result,
        "top_10": ranked[:10],
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = aggregate_metrics(case["metrics"] for case in cases)
    return {
        **metrics,
        "zero_result_rate": round(mean(case["zero_result"] for case in cases), 4),
        "relevant_candidate_yield": round(
            mean(case["relevant_candidate_yield"] for case in cases), 3
        ),
        "candidate_recall": round(mean(case["candidate_recall"] for case in cases), 4),
        "unique_useful_urls": round(mean(case["unique_useful_urls"] for case in cases), 3),
        "requests_per_query": round(mean(case["requests"] for case in cases), 3),
        "variant_attempts_per_query": round(mean(case["variant_attempts"] for case in cases), 3),
        "latency_per_query_ms": round(
            mean(case["simulated_external_latency_ms"] for case in cases), 2
        ),
        "rounds_per_query": round(mean(case["rounds"] for case in cases), 3),
    }


def evaluate() -> dict[str, Any]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    queries = payload["queries"]
    started = time.perf_counter()
    strategies: dict[str, Any] = {}
    all_cases: dict[str, list[dict[str, Any]]] = {}
    for strategy in STRATEGIES:
        cases = [evaluate_case(query, strategy, SearchMode.BALANCED) for query in queries]
        all_cases[strategy.name] = cases
        strategies[strategy.name] = _aggregate(cases)
    final_cases = all_cases[STRATEGIES[-1].name]
    mode_profiles = {}
    for mode in SearchMode:
        cases = [evaluate_case(query, STRATEGIES[-1], mode) for query in queries]
        mode_profiles[mode.value] = _aggregate(cases)
    segment_metrics: dict[str, Any] = {}
    for field in ("language", "class"):
        values = sorted({case[field] for case in final_cases})
        segment_metrics[field] = {
            value: _aggregate([case for case in final_cases if case[field] == value])
            for value in values
        }
    result = {
        "schema": "mirsad.mafer-phase2-planning-benchmark-result",
        "version": "1.0",
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "queries": len(queries),
        "judgment_unit": "retrieval action and unique useful URL",
        "not_a_frozen_relevance_holdout": True,
        "strategies": strategies,
        "modes": mode_profiles,
        "segments": segment_metrics,
        "cases": final_cases,
        "runtime_ms": round((time.perf_counter() - started) * 1000, 2),
        "external_blocking_policy": (
            "CAPTCHA_BLOCKED and ENGINE_UNAVAILABLE are excluded from successful "
            "zero-result judgments; this deterministic benchmark injects healthy transport."
        ),
    }
    JSON_REPORT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    output = evaluate()
    print(json.dumps(output, ensure_ascii=False, indent=2))
