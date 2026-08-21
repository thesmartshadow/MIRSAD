from __future__ import annotations

import asyncio
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import Settings
from ..connectors import (
    BaseConnector,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorSearchOptions,
)
from ..domains.analytics import build_analytics
from ..domains.clustering import build_cluster_candidate_plan, cluster_items
from ..domains.deduplication import (
    DeduplicationItem,
    canonicalize_url,
    content_fingerprint,
    cross_source_score,
    find_duplicate_groups,
)
from ..domains.engagement import normalize_engagement, social_reach
from ..domains.query import (
    ProcessedQuery,
    fts_query,
    normalize_text,
    process_query,
    resolve_content_language,
)
from ..domains.ranking import (
    ScoreComponents,
    calculate_score,
    is_candidate_match,
    relevance_score,
)
from ..domains.semantic import (
    SemanticDocument,
    SemanticRanker,
    SemanticScores,
    build_semantic_ranker,
    cluster_score_in_worker,
    score_in_worker,
)
from ..mafer.aliases import EntityAliasRepository
from ..mafer.assessment import (
    CandidateEvidence,
    StopReason,
    assess_uncertainty,
    classify_retrieval_outcome,
    decide_stop,
    marginal_evidence_gain,
)
from ..mafer.calibration import (
    ObservableSearchEvidence,
    calibrated_uncertainty,
    saturation_decision,
)
from ..mafer.evidence import evidence_completeness
from ..mafer.evidence_graph import EvidenceGraphRepository
from ..mafer.expansion import propose_evidence_expansions
from ..mafer.intent import IntentLabel, TemporalIntent
from ..mafer.lattice import (
    QueryLattice,
    QueryVariant,
    QueryVariantType,
    append_evidence_variants,
)
from ..mafer.learning import OutcomeRecorder, record_shadow_comparison
from ..mafer.planning import AdaptiveSearchPlanner
from ..mafer.shadow_ranking import (
    ShadowRankedItem,
    fusion_order,
    near_tie_diversity_order,
    query_aware_lexical_weight,
    shadow_ranking_summary,
)
from ..mafer.versions import SHADOW_STOP_MODEL_VERSION
from ..models import (
    AnalyticsRecord,
    AuditEvent,
    Cluster,
    ClusterMember,
    ConnectorRunRecord,
    ContentItem,
    ContentMetric,
    ContentScore,
    DuplicateGroup,
    DuplicateGroupMember,
    EngineUtilityObservation,
    SearchQuery,
    SearchResult,
    SearchSession,
    Setting,
    Source,
    SourceHealth,
    SourceUtilityObservation,
)
from ..schemas import SearchRequest, SortMode


@dataclass(slots=True)
class ConnectorRun:
    source: str
    items: list[ConnectorItem]
    latency_ms: float
    error: ConnectorError | None = None
    http_status: int | None = None
    raw_result_count: int = 0
    fetched_result_count: int = 0
    schema_valid_count: int = 0
    query_match_count: int = 0
    time_eligible_count: int = 0
    normalized_result_count: int = 0
    malformed_count: int = 0
    attempt_count: int = 0
    attempt_latencies_ms: tuple[float, ...] = ()
    total_latency_ms: float = 0
    circuit_breaker_state: str = "closed"
    details: dict[str, Any] = dataclass_field(default_factory=dict)


def _since(time_range: str) -> datetime | None:
    durations = {"24h": timedelta(days=1), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    duration = durations.get(time_range)
    return datetime.now(UTC) - duration if duration else None


class SearchService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        connectors: dict[str, BaseConnector],
        semantic_ranker: SemanticRanker | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.connectors = connectors
        self.semantic_ranker = semantic_ranker or build_semantic_ranker(settings)
        self.event_sink = event_sink
        self._source_cache: dict[str, Source] = {}

    def _emit(self, event: str, **data: Any) -> None:
        if self.event_sink is not None:
            self.event_sink(event, data)

    async def execute(self, request: SearchRequest, *, session_id: str | None = None) -> str:
        started = perf_counter()
        self._emit("search.started", query=request.query, mode=request.search_mode.value)
        processed = process_query(request.query, exact_phrase=request.exact_phrase)
        planning_started = perf_counter()
        self._emit("planning.started", source_selection=request.source_selection)
        planning = AdaptiveSearchPlanner(self.db, self.connectors).prepare(
            processed,
            selected_sources=request.sources,
            source_selection=request.source_selection,
            mode=request.search_mode,
            explicit_time_range=request.time_range.value,
        )
        lattice = planning.lattice
        search_trace = planning.initial_trace()
        planning_duration_ms = round((perf_counter() - planning_started) * 1000, 2)
        planned_sources = [
            source for round_sources in planning.resources.rounds for source in round_sources
        ]
        self._emit(
            "planning.completed",
            elapsed_ms=planning_duration_ms,
            intent=[label.value for label in planning.fingerprint.labels],
            variant_count=len(lattice.variants),
            selected_sources=planned_sources,
            round_count=len(planning.resources.rounds),
        )
        for source in planned_sources:
            self._emit(
                "source.selected",
                source=source,
                acquisition_mode=self.connectors[source].active_acquisition_mode(),
            )
        if request.source_selection == "auto":
            for source, connector in sorted(self.connectors.items()):
                if source in planned_sources or source == "mock":
                    continue
                configured, reason = connector.validate_configuration()
                if (
                    connector.active_acquisition_mode() == "WEB_INDEX"
                    and not self.settings.searxng_enabled
                ):
                    category = "web_discovery_disabled"
                elif connector.metadata.support_level == "restricted_access":
                    category = "restricted"
                elif not configured:
                    category = "unconfigured"
                else:
                    category = "not_selected"
                self._emit(
                    "source.skipped",
                    source=source,
                    acquisition_mode=connector.active_acquisition_mode(),
                    error_category=category,
                    reason=reason,
                )
        web_sources = [
            source
            for source in planned_sources
            if (
                source in self.connectors
                and getattr(self.connectors[source], "active_acquisition_mode", lambda: "")()
                == "WEB_INDEX"
            )
        ]

        def allocate(total: int, keys: list[str]) -> dict[str, int]:
            if total <= 0 or not keys:
                return {key: 0 for key in keys}
            quotient, remainder = divmod(total, len(keys))
            return {
                key: quotient + int(index < remainder) for index, key in enumerate(sorted(keys))
            }

        engine_call_allocations = allocate(planning.budget.max_discovery_engine_calls, web_sources)
        discovered_url_allocations = allocate(planning.budget.max_discovered_urls, web_sources)
        engine_calls_remaining = dict(engine_call_allocations)
        discovered_urls_remaining = dict(discovered_url_allocations)
        historical_sources = [
            source
            for source in web_sources
            if bool(request.source_options.get(source, {}).get("historical"))
        ]
        historical_call_allocations = allocate(
            planning.budget.max_historical_calls, historical_sources
        )
        historical_calls_remaining = dict(historical_call_allocations)
        query_row = SearchQuery(
            original_query=processed.original,
            normalized_query=processed.normalized,
            detected_language=processed.language,
            tokens=list(processed.tokens),
            variants=list(lattice.texts()),
            exact_phrase=processed.exact_phrase,
        )
        self.db.add(query_row)
        self.db.flush()
        parameters = request.model_dump(mode="json")
        parameters["exact_phrase"] = processed.exact_phrase
        session = SearchSession(
            id=session_id or str(__import__("uuid").uuid4()),
            query_id=query_row.id,
            sources=planned_sources,
            parameters=parameters,
        )
        self.db.add(session)
        self.db.add(
            AuditEvent(
                event_type="search_started",
                message="Search collection started",
                context={"session_id": session.id, "sources": planned_sources},
            )
        )
        self.db.commit()

        collection_since = _since(request.time_range.value)
        connector_started = perf_counter()
        completion_order: list[str] = []
        runs: list[ConnectorRun] = []
        accumulated_items = list(planning.local_memory.items)
        seen_round_urls = {item.canonical_url for item in accumulated_items}
        seen_round_sources = {item.source for item in accumulated_items}
        requests_used = 0
        stop_reason: StopReason | None = None
        queried_sources: set[str] = set()
        successful_sources: set[str] = set()
        source_completions = 0
        source_fetched = 0
        source_matched = 0

        local_evidence = self._planning_candidate_evidence(accumulated_items, lattice)
        local_uncertainty = assess_uncertainty(
            local_evidence,
            unqueried_useful_sources=len(planned_sources),
        )
        search_trace["rounds"][0]["uncertainty"] = local_uncertainty.as_dict()
        if (
            request.source_selection == "auto"
            and planning.fingerprint.temporal_intent == TemporalIntent.TIME_NEUTRAL
            and len(local_evidence) >= request.limit
            and local_uncertainty.level.value == "LOW"
        ):
            stop_reason = StopReason.SATISFIED
            search_trace["rounds"][0]["decision"] = StopReason.SATISFIED.value

        execution_rounds = list(planning.resources.rounds)
        if planning.budget.max_rounds > len(execution_rounds) and self._secondary_variants(
            lattice, round_number=2
        ):
            execution_rounds.extend(
                () for _ in range(planning.budget.max_rounds - len(execution_rounds))
            )

        for round_index, round_sources in enumerate(execution_rounds, start=1):
            if stop_reason is not None:
                break
            if perf_counter() - started >= planning.budget.max_wall_clock_seconds:
                stop_reason = StopReason.TIME_BUDGET
                break
            remaining_requests = planning.budget.max_source_calls - requests_used
            active_sources = list(round_sources[: max(0, remaining_requests)])
            repeat_variants = self._secondary_variants(
                lattice,
                round_number=round_index,
            )
            if round_index > 1 and repeat_variants and remaining_requests > len(active_sources):
                utility_order = [item.source for item in planning.resources.ordered]
                repeat_sources = [
                    source
                    for source in utility_order
                    if source in successful_sources and source not in active_sources
                ]
                active_sources.extend(repeat_sources[: remaining_requests - len(active_sources)])
            had_planned_work = bool(active_sources)
            active_sources = [
                source
                for source in active_sources
                if source not in web_sources
                or (
                    engine_calls_remaining.get(source, 0) > 0
                    and discovered_urls_remaining.get(source, 0) > 0
                )
            ]
            if not active_sources:
                stop_reason = (
                    StopReason.REQUEST_BUDGET
                    if remaining_requests <= 0 or had_planned_work
                    else StopReason.SATISFIED
                    if accumulated_items
                    else StopReason.SOURCE_EXHAUSTION
                )
                break
            round_started = perf_counter()

            current_lattice = lattice
            current_round = round_index
            first_attempts = {source: source not in queried_sources for source in active_sources}
            round_engine_allocations: dict[str, int] = {}
            round_url_allocations: dict[str, int] = {}
            round_historical_allocations: dict[str, int] = {}
            for source in active_sources:
                if source not in web_sources:
                    continue
                reserve_for_next_round = bool(
                    first_attempts[source]
                    and round_index < planning.budget.max_rounds
                    and self._secondary_variants(lattice, round_number=round_index + 1)
                )
                divisor = 2 if reserve_for_next_round else 1
                engine_allowance = max(1, (engine_calls_remaining[source] + divisor - 1) // divisor)
                url_allowance = max(1, (discovered_urls_remaining[source] + divisor - 1) // divisor)
                round_engine_allocations[source] = engine_allowance
                round_url_allocations[source] = url_allowance
                engine_calls_remaining[source] -= engine_allowance
                discovered_urls_remaining[source] -= url_allowance
                if source in historical_calls_remaining:
                    historical_allowance = min(1, historical_calls_remaining[source])
                    round_historical_allocations[source] = historical_allowance
                    historical_calls_remaining[source] -= historical_allowance

            async def run_and_record(
                source: str,
                round_lattice: QueryLattice = current_lattice,
                round_number: int = current_round,
                attempt_map: dict[str, bool] = first_attempts,
                engine_allowances: dict[str, int] = round_engine_allocations,
                url_allowances: dict[str, int] = round_url_allocations,
                historical_allowances: dict[str, int] = round_historical_allocations,
            ) -> ConnectorRun:
                nonlocal source_completions, source_fetched, source_matched
                self._emit("source.started", source=source, round=round_number)
                run = await self._run_connector(
                    source,
                    processed,
                    request,
                    collection_since,
                    lattice=round_lattice,
                    search_round=round_number,
                    max_discovery_engine_calls=engine_allowances.get(source, 0),
                    max_discovered_urls=url_allowances.get(source, 0),
                    max_historical_calls=historical_allowances.get(source, 0),
                    first_attempt=attempt_map[source],
                )
                completion_order.append(source)
                source_completions += 1
                source_fetched += run.fetched_result_count
                source_matched += run.query_match_count
                source_payload = {
                    "source": source,
                    "round": round_number,
                    "elapsed_ms": round(run.latency_ms, 2),
                    "fetched": run.fetched_result_count,
                    "matched": run.query_match_count,
                    "normalized": run.normalized_result_count,
                    "error_category": run.error.code if run.error else None,
                }
                if run.error and run.items:
                    self._emit("source.degraded", **source_payload)
                elif run.error:
                    self._emit("source.failed", **source_payload)
                else:
                    self._emit("source.completed", **source_payload)
                self._emit(
                    "collection.progress",
                    completed_sources=source_completions,
                    selected_sources=len(planned_sources),
                    fetched=source_fetched,
                    matched=source_matched,
                )
                return run

            remaining_time = max(
                0.01,
                planning.budget.max_wall_clock_seconds - (perf_counter() - started),
            )
            tasks = {
                asyncio.create_task(run_and_record(source)): source for source in active_sources
            }
            done, pending = await asyncio.wait(tasks, timeout=remaining_time)
            round_runs = [task.result() for task in done if not task.cancelled()]
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
                for task in sorted(pending, key=lambda value: tasks[value]):
                    source = tasks[task]
                    completion_order.append(source)
                    round_runs.append(
                        ConnectorRun(
                            source=source,
                            items=[],
                            latency_ms=remaining_time * 1000,
                            error=ConnectorError(
                                source,
                                "timeout",
                                "Search budget expired before this source completed",
                            ),
                            total_latency_ms=remaining_time * 1000,
                            circuit_breaker_state="budget_exhausted",
                            details={"budget_exhausted": True},
                        )
                    )
                    source_completions += 1
                    self._emit(
                        "source.failed",
                        source=source,
                        round=current_round,
                        elapsed_ms=round(remaining_time * 1000, 2),
                        fetched=0,
                        matched=0,
                        normalized=0,
                        error_category="time_budget_exceeded",
                    )
                stop_reason = StopReason.TIME_BUDGET
            round_runs.sort(key=lambda run: active_sources.index(run.source))
            requests_used += len(round_runs)
            runs.extend(round_runs)
            queried_sources.update(run.source for run in round_runs)
            successful_sources.update(run.source for run in round_runs if run.error is None)
            round_items = [item for run in round_runs for item in run.items]
            previous_url_count = len(seen_round_urls)
            previous_source_count = len(seen_round_sources)
            seen_round_urls.update(item.canonical_url for item in round_items)
            seen_round_sources.update(item.source for item in round_items)
            accumulated_items.extend(round_items)
            current_evidence = self._planning_candidate_evidence(accumulated_items, lattice)
            uncertainty = assess_uncertainty(
                current_evidence,
                degraded_sources=sum(run.error is not None for run in runs),
                unqueried_useful_sources=sum(
                    len(values) for values in execution_rounds[round_index:]
                )
                + int(
                    round_index < planning.budget.max_rounds
                    and bool(self._secondary_variants(lattice, round_number=round_index + 1))
                ),
            )
            round_gain = marginal_evidence_gain(
                round_index,
                new_canonical_urls=len(seen_round_urls) - previous_url_count,
                new_admitted_candidates=len(
                    {
                        item.canonical_url
                        for item in round_items
                        if self._matches_lattice(item, lattice)
                    }
                ),
                new_platforms=len(seen_round_sources) - previous_source_count,
                network_requests=len(round_runs),
                elapsed_ms=(perf_counter() - round_started) * 1000,
            )
            remaining_sources = sum(len(values) for values in execution_rounds[round_index:])
            if (
                round_index < planning.budget.max_rounds
                and self._secondary_variants(lattice, round_number=round_index + 1)
                and successful_sources
            ):
                remaining_sources += 1
            previous_external_round = next(
                (value for value in reversed(search_trace["rounds"]) if value.get("round", 0) > 0),
                None,
            )
            shadow_observable = self._shadow_observable(
                current_evidence,
                round_number=round_index,
                healthy_unqueried_sources=remaining_sources,
                degraded_sources=sum(run.error is not None for run in runs),
                current_unique_gain=round_gain.new_canonical_urls,
                current_admitted_gain=round_gain.new_admitted_candidates,
                previous_round=previous_external_round,
            )
            shadow_uncertainty = calibrated_uncertainty(
                shadow_observable,
                fingerprint=planning.fingerprint,
            )
            shadow_saturation = saturation_decision(
                shadow_observable,
                shadow_uncertainty,
                elapsed_seconds=perf_counter() - started,
                max_wall_clock_seconds=planning.budget.max_wall_clock_seconds,
                requests_used=requests_used,
                max_requests=planning.budget.max_source_calls,
                round_number=round_index,
                max_rounds=planning.budget.max_rounds,
            )
            search_trace["rounds"].append(
                {
                    "round": round_index,
                    "kind": "FEDERATED_EXTERNAL",
                    "sources": list(active_sources),
                    "repeated_sources": [
                        source for source in active_sources if not first_attempts[source]
                    ],
                    "requests": len(round_runs),
                    "discoveries": len(round_items),
                    "new_canonical_urls": round_gain.new_canonical_urls,
                    "candidate_gain": round_gain.new_admitted_candidates,
                    "failures": [
                        {
                            "source": run.source,
                            "code": run.error.code,
                        }
                        for run in round_runs
                        if run.error
                    ],
                    "source_outcomes": [
                        {
                            "source": run.source,
                            "outcome": classify_retrieval_outcome(
                                error_code=run.error.code if run.error else None,
                                completed=run.error is None,
                                result_count=len(run.items),
                            ).value,
                        }
                        for run in round_runs
                    ],
                    "query_variant_attempts": {
                        run.source: run.details.get("query_transformations", [])
                        for run in round_runs
                    },
                    "uncertainty": uncertainty.as_dict(),
                    "shadow_uncertainty": shadow_uncertainty.as_dict(),
                    "shadow_saturation": shadow_saturation.as_dict(),
                    "marginal_evidence_gain": round_gain.as_dict(),
                }
            )
            if stop_reason == StopReason.TIME_BUDGET:
                search_trace["rounds"][-1]["decision"] = stop_reason.value
                break
            if (
                round_index == 2
                and planning.budget.max_rounds >= 3
                and not planning.fingerprint.has(IntentLabel.IDENTIFIER)
            ):
                expansion_candidates = propose_evidence_expansions(
                    planning.fingerprint,
                    (
                        (
                            f"{item.source}:{item.external_id}",
                            f"{item.title or ''} {item.text}",
                        )
                        for item in accumulated_items
                    ),
                )
                lattice = append_evidence_variants(
                    lattice,
                    (
                        (item.term, item.confidence, item.drift_risk, item.reason)
                        for item in expansion_candidates
                        if item.accepted
                    ),
                )
                search_trace["gated_expansion"] = [item.as_dict() for item in expansion_candidates]
                search_trace["query_lattice"] = lattice.as_dict()
            if request.source_selection == "auto":
                stop_reason = decide_stop(
                    uncertainty=uncertainty,
                    gain=round_gain,
                    result_count=len(current_evidence),
                    user_limit=request.limit,
                    round_number=round_index,
                    max_rounds=planning.budget.max_rounds,
                    elapsed_seconds=perf_counter() - started,
                    max_wall_clock_seconds=planning.budget.max_wall_clock_seconds,
                    requests_used=requests_used,
                    max_requests=planning.budget.max_source_calls,
                    useful_unqueried_sources=remaining_sources,
                    available_sources=len(planned_sources),
                    must_attempt_more=bool(
                        round_index < planning.budget.max_rounds
                        and self._secondary_variants(lattice, round_number=round_index + 1)
                        and successful_sources
                    ),
                )
                if stop_reason is not None:
                    search_trace["rounds"][-1]["decision"] = stop_reason.value
                    break
                search_trace["rounds"][-1]["decision"] = "CONTINUE"
        if stop_reason is None:
            if not planned_sources:
                stop_reason = StopReason.NO_AVAILABLE_SOURCES
            elif accumulated_items:
                stop_reason = StopReason.SATISFIED
            else:
                stop_reason = StopReason.SOURCE_EXHAUSTION
        connector_duration_ms = round((perf_counter() - connector_started) * 1000, 2)
        search_trace["stop_reason"] = stop_reason.value
        search_trace["requests_used"] = requests_used
        search_trace["discovery_budget"] = {
            "engine_calls_allocated": engine_call_allocations,
            "engine_calls_remaining": engine_calls_remaining,
            "discovered_urls_allocated": discovered_url_allocations,
            "discovered_urls_remaining": discovered_urls_remaining,
            "historical_calls_allocated": historical_call_allocations,
            "historical_calls_remaining": historical_calls_remaining,
        }
        search_trace["final_query_lattice"] = lattice.as_dict()
        warnings = [run.error.as_dict() for run in runs if run.error]
        if stop_reason == StopReason.NO_AVAILABLE_SOURCES and not accumulated_items:
            warnings.append(
                {
                    "source": "mafer",
                    "code": "no_available_sources",
                    "message": "No configured source is currently available for this query",
                    "retryable": False,
                    "status_code": None,
                }
            )
        session.warnings = warnings
        self._update_health(runs)
        self._persist_connector_runs(session.id, runs)
        for run in runs:
            if run.error:
                self.db.add(
                    AuditEvent(
                        event_type="connector_failed",
                        level="warning",
                        message=run.error.message,
                        context={
                            "session_id": session.id,
                            "source": run.source,
                            "code": run.error.code,
                        },
                    )
                )

        items_by_source: dict[str, list[ConnectorItem]] = {}
        for item in planning.local_memory.items:
            if item.source in self.connectors:
                items_by_source.setdefault(item.source, []).append(item)
        for run in runs:
            items_by_source.setdefault(run.source, []).extend(run.items)
        eligible_by_source: dict[str, list[ConnectorItem]] = {}
        for source_key, raw_items in items_by_source.items():
            source_items: list[ConnectorItem] = []
            seen_source_items: set[tuple[str, str]] = set()
            for raw_item in raw_items:
                identity = (raw_item.source, raw_item.external_id)
                if identity in seen_source_items:
                    continue
                seen_source_items.add(identity)
                content = f"{raw_item.title or ''} {raw_item.text}"
                completeness = evidence_completeness(raw_item)
                item = replace(
                    raw_item,
                    language=resolve_content_language(raw_item.language, content),
                    raw_metadata={
                        **raw_item.raw_metadata,
                        "evidence_completeness": completeness.as_dict(),
                    },
                )
                if not self._matches_lattice(item, lattice):
                    continue
                if request.language != "all" and item.language != request.language:
                    continue
                if not self._within_time_range(item.published_at, collection_since):
                    continue
                if self._matches_filters(item, request):
                    source_items.append(item)
            eligible_by_source[source_key] = source_items
        eligible_count_by_source = {
            source: len(items) for source, items in sorted(eligible_by_source.items())
        }
        per_source_limit = min(
            self.settings.max_result_limit,
            self.settings.source_pre_candidate_limit,
            max(request.limit, self.settings.semantic_candidate_limit),
        )
        candidate_queues = {
            source: sorted(
                source_items,
                key=lambda item: self._candidate_order_key(processed, item),
                reverse=True,
            )[:per_source_limit]
            for source, source_items in sorted(eligible_by_source.items())
        }
        collected: list[ConnectorItem] = []
        seen_external: set[tuple[str, str]] = set()
        position = 0
        while len(collected) < planning.budget.max_normalized_candidates:
            progressed = False
            for source in sorted(candidate_queues):
                source_candidates = candidate_queues[source]
                if position >= len(source_candidates):
                    continue
                item = source_candidates[position]
                identity = (item.source, item.external_id)
                if identity in seen_external:
                    continue
                seen_external.add(identity)
                collected.append(item)
                progressed = True
                if len(collected) >= planning.budget.max_normalized_candidates:
                    break
            if not progressed and all(
                position >= len(values) - 1 for values in candidate_queues.values()
            ):
                break
            position += 1
        alias_edges_added = self._observe_alias_evidence(planning, collected)
        search_trace["alias_edges_added"] = alias_edges_added
        search_trace["final_candidate_pool"] = {
            "matched_per_source": eligible_count_by_source,
            "admitted_per_source": dict(Counter(item.source for item in collected)),
            "admitted_total": len(collected),
        }
        admitted_by_source = Counter(item.source for item in collected)
        for source in sorted(set(eligible_count_by_source) | set(admitted_by_source)):
            self._emit(
                "source.progress",
                source=source,
                matched=eligible_count_by_source.get(source, 0),
                admitted=admitted_by_source.get(source, 0),
            )
        self._emit(
            "normalization.completed",
            matched=sum(eligible_count_by_source.values()),
            admitted=len(collected),
            admitted_per_source=dict(admitted_by_source),
        )
        persistence_started = perf_counter()
        collected_count_by_source = Counter(item.source for item in collected)
        persisted = [self._persist_item(item) for item in collected]
        self.db.commit()
        persistence_duration_ms = round((perf_counter() - persistence_started) * 1000, 2)
        self._emit(
            "persistence.completed",
            elapsed_ms=persistence_duration_ms,
            persisted=len(persisted),
        )

        dedupe_started = perf_counter()
        dedupe_items = [
            DeduplicationItem(
                key=item.id,
                source=source,
                canonical_url=item.canonical_url,
                title=item.title,
                text=item.text,
                published_at=item.published_at,
            )
            for item, source in persisted
        ]
        duplicate_sets = find_duplicate_groups(dedupe_items)
        group_by_item, cross_by_item, duplicate_meta = self._persist_duplicate_groups(
            session.id, duplicate_sets, persisted
        )
        dedupe_duration_ms = round((perf_counter() - dedupe_started) * 1000, 2)
        ranking_started = perf_counter()
        self._emit("ranking.started", candidates=len(persisted))
        bm25 = self._bm25_scores(processed, [item.id for item, _ in persisted])
        lexical_candidates = sorted(
            persisted,
            key=lambda pair: self._lexical_ranking_key(
                processed, pair[0], bm25.get(pair[0].id, 0), pair[1]
            ),
            reverse=True,
        )
        semantic_candidates = self._select_semantic_candidates(
            lexical_candidates, self.settings.semantic_candidate_limit
        )
        semantic_documents = [
            SemanticDocument(key=item.id, title=item.title, text=item.text)
            for item, _source in semantic_candidates
        ]
        if getattr(self.semantic_ranker, "enabled", True):
            semantic = await score_in_worker(self.semantic_ranker, processed, semantic_documents)
        else:
            semantic = self.semantic_ranker.score(processed, semantic_documents)
        semantic_candidate_ids = set(semantic.scores)
        item_ids = [item.id for item, _ in persisted]
        metrics_by_item = {
            metric.content_item_id: metric
            for metric in self.db.scalars(
                select(ContentMetric).where(ContentMetric.content_item_id.in_(item_ids))
            ).all()
        }
        confidence_by_source = {
            source.key: source.confidence
            for source in self.db.scalars(
                select(Source).where(Source.key.in_({source for _, source in persisted}))
            ).all()
        }
        scores: dict[int, ScoreComponents] = {}
        for item, source_key in persisted:
            metric = metrics_by_item.get(item.id)
            duplicate = duplicate_meta.get(item.id)
            score = calculate_score(
                query=processed,
                title=item.title,
                text=item.text,
                canonical_url=item.canonical_url,
                published_at=item.published_at,
                engagement=metric.normalized_engagement if metric else 0,
                source_confidence=confidence_by_source.get(source_key, 50),
                cross_source_presence=cross_by_item.get(item.id, 0),
                novelty=100 if not duplicate or duplicate["canonical"] == item.id else 40,
                bm25_normalized=bm25.get(item.id, 0),
                author_handle=item.author_handle,
                hashtags=item.hashtags,
                semantic_relevance=semantic.scores.get(item.id),
                semantic_similarity=semantic.similarities.get(item.id),
                semantic_weight=self.settings.semantic_relevance_weight,
                semantic_quality_budget=self.settings.semantic_quality_budget,
                weights=self._ranking_weights(),
                half_life_hours=self.settings.freshness_half_life_hours,
            )
            scores[item.id] = score
            self.db.add(
                ContentScore(
                    search_session_id=session.id,
                    content_item_id=item.id,
                    final_score=score.final_score,
                    relevance=score.relevance,
                    freshness=score.freshness,
                    engagement=score.engagement,
                    source_confidence=score.source_confidence,
                    cross_source_presence=score.cross_source_presence,
                    novelty=score.novelty,
                    spam_penalty=score.spam_penalty,
                    matched_terms=list(score.matched_terms),
                    explanation=score.explanation(),
                )
            )
        ranking_duration_ms = round((perf_counter() - ranking_started) * 1000, 2)
        self._emit(
            "ranking.completed",
            elapsed_ms=ranking_duration_ms,
            semantic_ms=semantic.duration_ms,
            semantic_state=semantic.state,
            semantic_candidates=len(semantic_candidates),
            cache_hits=semantic.cache_hits,
            cache_misses=semantic.cache_misses,
        )

        clustering_started = perf_counter()
        self._emit("clustering.started", candidates=min(len(persisted), request.limit))
        ordered = self._sort_items(
            persisted,
            scores,
            request.sort,
            semantic_candidate_ids=semantic_candidate_ids,
            duplicate_meta=duplicate_meta,
        )
        final_ordered = ordered[: request.limit]
        final_ids = {item.id for item, _source in final_ordered}
        final_dedupe_items = [item for item in dedupe_items if item.key in final_ids]
        final_duplicate_groups = [
            tuple(member for member in group.members if member in final_ids)
            for group in duplicate_sets
            if sum(member in final_ids for member in group.members) > 1
        ]
        cluster_plan = build_cluster_candidate_plan(
            final_dedupe_items,
            query_tokens=processed.tokens,
            duplicate_groups=final_duplicate_groups,
        )
        cluster_documents = [
            SemanticDocument(key=item.id, title=item.title, text=item.text)
            for item, _source in final_ordered
            if item.id in cluster_plan.representative_keys
        ]
        cluster_semantic = await cluster_score_in_worker(
            self.semantic_ranker,
            cluster_documents,
            cluster_plan.pairs,
        )
        clusters = cluster_items(
            final_dedupe_items,
            query_tokens=processed.tokens,
            duplicate_groups=final_duplicate_groups,
            semantic_similarities=cluster_semantic.similarities,
            candidate_plan=cluster_plan,
        )
        cluster_by_item, cluster_sizes = self._persist_clusters(session.id, clusters, scores)
        clustering_duration_ms = round((perf_counter() - clustering_started) * 1000, 2)
        self._emit(
            "clustering.completed",
            elapsed_ms=clustering_duration_ms,
            clusters=len(clusters),
        )
        production_order = [item.id for item, _source in ordered]
        shadow_fusion_order = fusion_order(
            [
                (
                    item.id,
                    source,
                    scores[item.id].lexical_relevance,
                    semantic.scores.get(item.id),
                )
                for item, source in ordered
            ],
            lexical_weight=query_aware_lexical_weight(planning.fingerprint),
        )
        shadow_diversity_order = near_tie_diversity_order(
            [
                ShadowRankedItem(
                    item.id,
                    source,
                    scores[item.id].final_score,
                    cluster_by_item.get(item.id, f"item:{item.id}"),
                )
                for item, source in ordered
            ]
        )
        search_trace["shadow_ranking"] = shadow_ranking_summary(
            production_order=production_order,
            fusion=shadow_fusion_order,
            diversity=shadow_diversity_order,
            lexical_weight=query_aware_lexical_weight(planning.fingerprint),
        )
        final_evidence = [
            CandidateEvidence(
                canonical_url=item.canonical_url,
                source=source,
                metadata_completeness=float(
                    (item.raw_metadata or {}).get("evidence_completeness", {}).get("score", 0.5)
                ),
                variant_ids=tuple(
                    str(value)
                    for value in (item.raw_metadata or {}).get("query_variants_that_found_it", ())
                ),
                engine_ids=tuple(
                    str(value)
                    for value in (item.raw_metadata or {}).get("engines_that_found_it", ())
                ),
                lexical_strength=scores[item.id].lexical_relevance,
                semantic_strength=semantic.scores.get(item.id),
            )
            for item, source in final_ordered
        ]
        search_trace["post_ranking_uncertainty"] = assess_uncertainty(final_evidence).as_dict()
        search_trace["final_ranking_pipeline"] = {
            "candidate_admission": "bounded_fair_per_source_union",
            "lexical_admission": True,
            "semantic_candidate_limit": self.settings.semantic_candidate_limit,
            "semantic_candidate_selection": "source_opportunity_round_robin",
            "semantic_state": semantic.state,
            "lexical_weight": round(1 - self.settings.semantic_relevance_weight, 4),
            "semantic_weight": self.settings.semantic_relevance_weight,
            "secondary_quality_budget": self.settings.semantic_quality_budget,
            "final_limit": request.limit,
            "stories_identified": len(clusters),
            "aliases_observed": alias_edges_added,
        }
        for rank, (item, _source_key) in enumerate(final_ordered, start=1):
            self.db.add(
                SearchResult(
                    search_session_id=session.id,
                    content_item_id=item.id,
                    rank=rank,
                    duplicate_group_id=group_by_item.get(item.id),
                    cluster_id=cluster_by_item.get(item.id),
                )
            )

        duration_ms = int((perf_counter() - started) * 1000)
        final_identity = {
            group_by_item.get(item.id) or f"item:{item.id}" for item, _source in final_ordered
        }
        unique_count = len(final_identity)
        all_unique_count = len(persisted) - sum(len(group.members) - 1 for group in duplicate_sets)
        session.result_count = len(final_ordered)
        session.unique_count = unique_count
        session.duration_ms = duration_ms
        session.status = (
            "partial"
            if warnings and (persisted or any(run.error is None for run in runs))
            else "failed"
            if (warnings and not persisted)
            or (stop_reason == StopReason.NO_AVAILABLE_SOURCES and not persisted)
            else "completed"
        )
        session.completed_at = datetime.now(UTC)
        outcome = self._search_outcome(
            request=request,
            planned_sources=planned_sources,
            runs=runs,
            result_count=len(final_ordered),
        )
        public_id_by_database_id = {item.id: item.public_id for item, _source in final_ordered}
        final_count_by_source = Counter(source for _item, source in final_ordered)
        completion_positions: list[int] = []
        consumed_completion_positions: Counter[str] = Counter()
        positions_by_source = {
            source: [
                position
                for position, completed_source in enumerate(completion_order, 1)
                if completed_source == source
            ]
            for source in set(completion_order)
        }
        for run in runs:
            occurrence = consumed_completion_positions[run.source]
            completion_positions.append(positions_by_source[run.source][occurrence])
            consumed_completion_positions[run.source] += 1
        session.diagnostics = {
            "query": {
                "original": processed.original,
                "normalized": processed.normalized,
                "variants": list(processed.variants),
                "variant_details": [
                    {"variant": variant, "reason": reason}
                    for variant, reason in processed.variant_reasons
                ],
                "tokens": list(processed.tokens),
                "token_sequence": list(processed.sequence),
                "exact_phrase": processed.exact_phrase,
                "intent": processed.intent,
                "query_type": semantic.query_type,
            },
            "selected_sources": planned_sources,
            "outcome": outcome,
            "connector_completion_order": completion_order,
            "connector_total_latency_ms": connector_duration_ms,
            "connectors": [
                {
                    "source": run.source,
                    "latency_ms": round(run.latency_ms, 2),
                    "total_connector_latency_ms": round(run.total_latency_ms or run.latency_ms, 2),
                    "http_status": run.http_status,
                    "fetched_results": run.fetched_result_count,
                    "schema_valid_results": run.schema_valid_count,
                    "query_matching_results": run.query_match_count,
                    "time_eligible_results": run.time_eligible_count,
                    "raw_results": run.raw_result_count,
                    "normalized_results": run.normalized_result_count,
                    "final_matching_results": eligible_count_by_source.get(run.source, 0),
                    "collected_results": collected_count_by_source.get(run.source, 0),
                    "candidate_admitted_results": collected_count_by_source.get(run.source, 0),
                    "final_top_results": final_count_by_source.get(run.source, 0),
                    "completion_position": completion_position,
                    "malformed_records": run.malformed_count,
                    "attempt_count": run.attempt_count,
                    "attempt_latencies_ms": list(run.attempt_latencies_ms),
                    "circuit_breaker_state": run.circuit_breaker_state,
                    "status": self._health_state(run.error, partial_success=bool(run.items)),
                    "error_category": run.error.code if run.error else None,
                    "query_variant_attempts": run.details.get("query_variant_attempts", []),
                    "query_variant_texts": run.details.get("query_variant_texts", []),
                    "query_transformations": run.details.get("query_transformations", []),
                    "mode": run.details.get("mode"),
                    "instances": run.details.get("instances"),
                    "instance_results": run.details.get("instance_results"),
                    "local_query_matches": run.details.get(
                        "local_query_matches", run.query_match_count
                    ),
                    "duplicates": run.details.get("duplicates", 0),
                    "acquisition_mode": run.details.get("acquisition_mode"),
                    "cache_state": run.details.get("cache_state"),
                    "engine_telemetry": run.details.get("engine_telemetry"),
                    "historical_state": run.details.get("historical_state"),
                }
                for run, completion_position in zip(runs, completion_positions, strict=True)
            ],
            "candidate_admission": {
                "per_source_limit": per_source_limit,
                "matched_per_source": eligible_count_by_source,
                "admitted_per_source": dict(collected_count_by_source),
                "final_top_per_source": dict(final_count_by_source),
                "admitted_total": len(persisted),
                "final_global_cap": request.limit,
                "relevance_distribution_by_source": self._source_relevance_distributions(
                    persisted, scores
                ),
            },
            "duplicates_detected": len(persisted) - all_unique_count,
            "final_unique_result_count": unique_count,
            "phase_timings_ms": {
                "adaptive_planning": planning_duration_ms,
                "connector_collection": connector_duration_ms,
                "persistence": persistence_duration_ms,
                "deduplication": dedupe_duration_ms,
                "ranking": ranking_duration_ms,
                "semantic_reranking": semantic.duration_ms,
                "clustering": clustering_duration_ms,
                "total": duration_ms,
            },
            "score_component_distributions": self._score_distributions(scores),
            "ranking": {
                **self._semantic_diagnostics(semantic),
                "semantic_candidates_per_source": dict(
                    Counter(source for _item, source in semantic_candidates)
                ),
                "semantic_candidate_selection": "source_opportunity_round_robin",
            },
            "clustering": {
                "strategy": "distinctive_blocks_complete_linkage",
                "candidate_pairs": len(cluster_plan.pairs),
                "lexical_block_pairs": cluster_plan.lexical_block_pairs,
                "temporal_block_pairs": cluster_plan.temporal_block_pairs,
                "capped_pairs": cluster_plan.capped_pairs,
                "semantic_state": cluster_semantic.state,
                "semantic_model": cluster_semantic.model,
                "semantic_model_version": cluster_semantic.model_version,
                "semantic_duration_ms": cluster_semantic.duration_ms,
                "embedding_cache_hits": cluster_semantic.cache_hits,
                "embedding_cache_misses": cluster_semantic.cache_misses,
                "suspicious_cluster_count": sum(cluster.suspicious for cluster in clusters),
                "multi_member_clusters": [
                    {
                        "representative_title": cluster.representative_title,
                        "member_count": len(cluster.members),
                        "member_ids": [
                            public_id_by_database_id[item_id] for item_id in cluster.members
                        ],
                        "member_similarities": {
                            str(item_id): cluster.member_similarities.get(item_id, 1.0)
                            for item_id in cluster.members
                        },
                        "member_reasons": {
                            str(item_id): list(cluster.member_reasons.get(item_id, ()))
                            for item_id in cluster.members
                        },
                        "suspicious": cluster.suspicious,
                        "suspicious_reason": cluster.suspicious_reason,
                    }
                    for cluster in clusters
                    if len(cluster.members) > 1 or cluster.suspicious
                ],
            },
            "mafer": search_trace,
        }
        self._persist_phase3_observations(
            session=session,
            processed=processed,
            planning=planning,
            runs=runs,
            collected=collected,
            final_ordered=final_ordered,
            cluster_by_item=cluster_by_item,
        )
        analytics_items = [
            {
                "source": source,
                "score": scores[item.id].final_score,
                "published_at": item.published_at,
                "language": item.language,
                "title": item.title,
                "text": item.text,
                "id": item.public_id,
                "category": self.connectors[source].metadata.category,
                "hashtags": item.hashtags,
                "mentions": item.mentions,
                "engagement": metrics_by_item[item.id].normalized_engagement
                if item.id in metrics_by_item and metrics_by_item[item.id].raw_metrics
                else None,
                "has_engagement_metrics": bool(
                    item.id in metrics_by_item and metrics_by_item[item.id].raw_metrics
                ),
                "social_reach": social_reach(
                    source,
                    metrics_by_item[item.id].normalized_engagement,
                    int(duplicate_meta.get(item.id, {}).get("source_count", 1)),
                )
                if item.id in metrics_by_item and metrics_by_item[item.id].raw_metrics
                else None,
            }
            for item, source in final_ordered
        ]
        analytics_windows = {
            "24h": ("1h", 24),
            "7d": ("6h", 28),
            "30d": ("24h", 30),
            "all": ("24h", 60),
        }
        analytics_bucket, analytics_bucket_count = analytics_windows[request.time_range.value]
        analytics = build_analytics(
            analytics_items,
            unique_count=session.unique_count,
            duration_ms=duration_ms,
            cluster_sizes=cluster_sizes,
            query_tokens=processed.tokens,
            bucket=analytics_bucket,
            bucket_count=analytics_bucket_count,
            include_all_time=request.time_range.value == "all",
        )
        self.db.add(
            AnalyticsRecord(search_session_id=session.id, metric_key="snapshot", value=analytics)
        )
        self.db.add(
            AuditEvent(
                event_type="search_completed",
                message="Search collection completed",
                context={
                    "session_id": session.id,
                    "status": session.status,
                    "result_count": session.result_count,
                    "duration_ms": duration_ms,
                },
            )
        )
        self.db.commit()
        terminal_event = "search.partial" if session.status == "partial" else "search.completed"
        if session.status == "failed":
            terminal_event = "search.failed"
        self._emit(
            terminal_event,
            status=session.status,
            result_count=session.result_count,
            unique_count=session.unique_count,
            cluster_count=len(clusters),
            duration_ms=duration_ms,
            stop_reason=stop_reason.value,
            warning_count=len(warnings),
        )
        return session.id

    @staticmethod
    def _shadow_observable(
        evidence: list[CandidateEvidence],
        *,
        round_number: int,
        healthy_unqueried_sources: int,
        degraded_sources: int,
        current_unique_gain: int,
        current_admitted_gain: int,
        previous_round: dict[str, Any] | None,
    ) -> ObservableSearchEvidence:
        sources = {item.source for item in evidence}
        completeness = (
            sum(item.metadata_completeness for item in evidence) / len(evidence)
            if evidence
            else 0.0
        )
        variant_supported = [item for item in evidence if item.variant_ids]
        coherent_variants = [item for item in variant_supported if len(set(item.variant_ids)) > 1]
        variant_agreement = (
            len(coherent_variants) / len(variant_supported) if variant_supported else 0.5
        )
        disagreements = [
            abs(item.lexical_strength - item.semantic_strength)
            for item in evidence
            if item.lexical_strength is not None and item.semantic_strength is not None
        ]
        disagreement = sum(disagreements) / len(disagreements) if disagreements else 0.0
        lexical = sorted(
            (item.lexical_strength for item in evidence if item.lexical_strength is not None),
            reverse=True,
        )
        rank_margin = lexical[0] - lexical[1] if len(lexical) > 1 else 0.0
        engines = {engine for item in evidence for engine in item.engine_ids}
        return ObservableSearchEvidence(
            candidate_count=len(evidence),
            source_count=len(sources),
            healthy_unqueried_sources=healthy_unqueried_sources,
            variant_agreement=variant_agreement,
            lexical_semantic_disagreement=disagreement,
            rank_margin=rank_margin,
            evidence_completeness=completeness,
            single_engine_dependence=bool(engines) and len(engines) == 1,
            degraded_sources=degraded_sources,
            round_number=round_number,
            previous_unique_gain=(
                int(previous_round.get("new_canonical_urls", 0)) if previous_round else None
            ),
            current_unique_gain=current_unique_gain,
            previous_admitted_gain=(
                int(previous_round.get("candidate_gain", 0)) if previous_round else None
            ),
            current_admitted_gain=current_admitted_gain,
        )

    def _persist_phase3_observations(
        self,
        *,
        session: SearchSession,
        processed: ProcessedQuery,
        planning: Any,
        runs: list[ConnectorRun],
        collected: list[ConnectorItem],
        final_ordered: list[tuple[ContentItem, str]],
        cluster_by_item: dict[int, str],
    ) -> None:
        recorder = OutcomeRecorder(self.db)
        recorder.record(
            "SEARCH_EXECUTED", session=session, context={"result_count": len(final_ordered)}
        )
        if not final_ordered:
            recorder.record("ZERO_RESULT", session=session)
        query_class = next(
            (
                label.value.casefold()
                for label in (
                    IntentLabel.IDENTIFIER,
                    IntentLabel.HANDLE,
                    IntentLabel.HASHTAG,
                    IntentLabel.EXACT_PHRASE,
                    IntentLabel.PERSON_LIKE,
                    IntentLabel.ENTITY_LIKE,
                    IntentLabel.EVENT_LIKE,
                    IntentLabel.TOPIC,
                    IntentLabel.AMBIGUOUS,
                )
                if planning.fingerprint.has(label)
            ),
            "unknown",
        )
        runs_by_source: dict[str, list[ConnectorRun]] = {}
        for run in runs:
            runs_by_source.setdefault(run.source, []).append(run)
            if run.error:
                recorder.record(
                    "SOURCE_FAILURE",
                    session=session,
                    source=run.source,
                    context={"category": run.error.code},
                )
            for telemetry in run.details.get("engine_telemetry", []) or []:
                returned = int(telemetry.get("returned_result_count", 0))
                target = int(telemetry.get("target_domain_result_count", 0))
                self.db.add(
                    EngineUtilityObservation(
                        search_session_id=session.id,
                        query_class=query_class,
                        engine=str(telemetry.get("engine", "unknown"))[:100],
                        target_platform=str(telemetry.get("target_platform", run.source))[:50],
                        request_count=1,
                        available=not bool(telemetry.get("error")),
                        target_domain_precision=target / max(1, returned),
                        canonical_yield=int(telemetry.get("accepted_canonical_result_count", 0)),
                        unique_yield=max(
                            0,
                            int(telemetry.get("accepted_canonical_result_count", 0))
                            - int(telemetry.get("duplicate_count", 0)),
                        ),
                        latency_ms=float(telemetry.get("latency_ms") or 0),
                        rate_limited=bool(telemetry.get("rate_limited")),
                        captcha_blocked=str(telemetry.get("current_state", "")).upper()
                        == "CAPTCHA_BLOCKED",
                        timed_out=bool(telemetry.get("timeout")),
                    )
                )
        final_counts = Counter(source for _item, source in final_ordered)
        collected_by_source = Counter(item.source for item in collected)
        unique_by_source = {
            source: len({item.canonical_url for item in collected if item.source == source})
            for source in collected_by_source
        }
        for source in planning.resources.ordered:
            source_runs = runs_by_source.get(source.source, [])
            returned = sum(run.query_match_count for run in source_runs)
            admitted = collected_by_source.get(source.source, 0)
            self.db.add(
                SourceUtilityObservation(
                    search_session_id=session.id,
                    query_class=query_class,
                    source=source.source,
                    selected=bool(source_runs),
                    available=source.available,
                    returned_count=returned,
                    unique_count=unique_by_source.get(source.source, 0),
                    admitted_count=admitted,
                    top_k_count=final_counts.get(source.source, 0),
                    latency_ms=sum(run.latency_ms for run in source_runs),
                    failure_category=next(
                        (run.error.code for run in source_runs if run.error), None
                    ),
                    duplicate_rate=(
                        1 - unique_by_source.get(source.source, 0) / admitted if admitted else 0
                    ),
                )
            )
        record_shadow_comparison(
            self.db,
            session_id=session.id,
            strategy_type="router",
            strategy_version=planning.shadow_resources.version,
            production_output={
                "ordered_sources": [item.source for item in planning.resources.ordered]
            },
            shadow_output=planning.shadow_resources.as_dict(),
            comparison={"changed": planning.shadow_resources.changed, "user_visible": False},
        )
        shadow_rounds = [
            {
                "round": value.get("round"),
                "uncertainty": value.get("shadow_uncertainty"),
                "decision": value.get("shadow_saturation"),
            }
            for value in (session.diagnostics or {}).get("mafer", {}).get("rounds", [])
            if value.get("shadow_saturation")
        ]
        record_shadow_comparison(
            self.db,
            session_id=session.id,
            strategy_type="stop_policy",
            strategy_version=SHADOW_STOP_MODEL_VERSION,
            production_output={
                "stop_reason": (session.diagnostics or {}).get("mafer", {}).get("stop_reason")
            },
            shadow_output={"rounds": shadow_rounds},
            comparison={"user_visible": False},
        )
        shadow_ranking = (session.diagnostics or {}).get("mafer", {}).get("shadow_ranking", {})
        for strategy_type, output in (
            ("query_fusion", shadow_ranking.get("fusion")),
            ("near_tie_diversity", shadow_ranking.get("near_tie_diversity")),
        ):
            if not output:
                continue
            record_shadow_comparison(
                self.db,
                session_id=session.id,
                strategy_type=strategy_type,
                strategy_version=str(output["version"]),
                production_output={"visible_result_count": session.result_count},
                shadow_output=output,
                comparison={
                    "order_changed": bool(output["order_changed"]),
                    "top_10_overlap": int(output["top_10_overlap"]),
                    "user_visible": False,
                },
            )
        graph = EvidenceGraphRepository(self.db)
        for item, source in final_ordered:
            graph.observe_result(
                query=processed.original,
                content_public_id=item.public_id,
                canonical_url=item.canonical_url,
                source=source,
                author_handle=item.author_handle,
                hashtags=item.hashtags,
                cluster_id=cluster_by_item.get(item.id),
                session_id=session.id,
            )

    async def _run_connector(
        self,
        source_key: str,
        query: ProcessedQuery,
        request: SearchRequest,
        since: datetime | None,
        *,
        lattice: QueryLattice,
        search_round: int,
        max_discovery_engine_calls: int,
        max_discovered_urls: int,
        max_historical_calls: int,
        first_attempt: bool,
    ) -> ConnectorRun:
        connector = self.connectors.get(source_key)
        if connector is None:
            return ConnectorRun(
                source_key,
                [],
                0,
                ConnectorError(source_key, "unknown_source", "Source is not supported"),
            )
        source_row = self.db.scalar(select(Source).where(Source.key == source_key))
        if source_row is not None and not source_row.enabled:
            return ConnectorRun(
                source_key,
                [],
                0,
                ConnectorError(source_key, "disabled", "Source is disabled"),
            )
        configured, reason = connector.validate_configuration()
        if not configured:
            state = connector.configuration_state()
            return ConnectorRun(
                source_key,
                [],
                0,
                ConnectorError(
                    source_key,
                    "restricted_access" if state == "restricted" else "unconfigured",
                    reason or "Source is not configured",
                ),
            )
        started = perf_counter()
        connector.last_diagnostics = ConnectorDiagnostics()
        try:
            connector_limit = min(
                self.settings.max_result_limit,
                self.settings.source_pre_candidate_limit,
                max(request.limit, self.settings.semantic_candidate_limit),
            )
            is_web_index = connector.active_acquisition_mode() == "WEB_INDEX"
            attempt_variants = self._variants_for_connector_attempt(
                lattice,
                round_number=search_round,
                first_attempt=first_attempt,
                web_index=is_web_index,
            )
            query_text = attempt_variants[0].text
            effective_source_options = {
                key: dict(value) for key, value in request.source_options.items()
            }
            items = await connector.search_with_options(
                query_text,
                limit=connector_limit,
                since=since,
                options=ConnectorSearchOptions(
                    exact_phrase=query.exact_phrase
                    or attempt_variants[0].transformation == QueryVariantType.EXACT,
                    language=request.language,
                    sort=request.sort.value,
                    content_types=tuple(request.content_types),
                    has_media=request.has_media,
                    has_links=request.has_links,
                    hashtags=tuple(request.hashtags),
                    source_options=effective_source_options,
                    original_query=query.original,
                    query_variants=tuple(item.text for item in attempt_variants),
                    query_variant_metadata=tuple(item.as_dict() for item in attempt_variants),
                    query_intent=query.intent,
                    time_range=request.time_range.value,
                    search_round=search_round,
                    search_mode=request.search_mode.value,
                    max_discovery_engine_calls=max_discovery_engine_calls,
                    max_discovered_urls=max_discovered_urls,
                    max_historical_calls=max_historical_calls,
                ),
            )
            diagnostic = connector.last_diagnostics
            partial_error = (
                ConnectorError(
                    source_key,
                    diagnostic.warning_code,
                    diagnostic.warning_message or "Source completed with warnings",
                    status_code=diagnostic.warning_status_code,
                )
                if diagnostic.warning_code
                else None
            )
            return ConnectorRun(
                source_key,
                items,
                (perf_counter() - started) * 1000,
                partial_error,
                http_status=diagnostic.http_status,
                raw_result_count=diagnostic.raw_result_count or len(items),
                fetched_result_count=diagnostic.fetched_result_count or len(items),
                schema_valid_count=diagnostic.schema_valid_count or len(items),
                query_match_count=diagnostic.query_match_count or len(items),
                time_eligible_count=diagnostic.time_eligible_count or len(items),
                normalized_result_count=diagnostic.normalized_result_count or len(items),
                malformed_count=diagnostic.malformed_count,
                attempt_count=diagnostic.attempt_count,
                attempt_latencies_ms=tuple(diagnostic.attempt_latencies_ms),
                total_latency_ms=diagnostic.total_latency_ms,
                circuit_breaker_state=diagnostic.circuit_breaker_state,
                details={
                    **dict(diagnostic.details),
                    "search_round": search_round,
                    "query_variant_attempts": [item.variant_id for item in attempt_variants],
                    "query_variant_texts": [item.text for item in attempt_variants],
                    "query_transformations": [
                        item.transformation.value for item in attempt_variants
                    ],
                },
            )
        except ConnectorError as exc:
            diagnostic = connector.last_diagnostics
            return ConnectorRun(
                source_key,
                [],
                (perf_counter() - started) * 1000,
                exc,
                http_status=exc.status_code or diagnostic.http_status,
                raw_result_count=diagnostic.raw_result_count,
                fetched_result_count=diagnostic.fetched_result_count,
                schema_valid_count=diagnostic.schema_valid_count,
                query_match_count=diagnostic.query_match_count,
                time_eligible_count=diagnostic.time_eligible_count,
                normalized_result_count=diagnostic.normalized_result_count,
                malformed_count=diagnostic.malformed_count,
                attempt_count=diagnostic.attempt_count,
                attempt_latencies_ms=tuple(diagnostic.attempt_latencies_ms),
                total_latency_ms=diagnostic.total_latency_ms,
                circuit_breaker_state=diagnostic.circuit_breaker_state,
                details=dict(diagnostic.details),
            )
        except (TypeError, ValueError, KeyError):
            return ConnectorRun(
                source_key,
                [],
                (perf_counter() - started) * 1000,
                ConnectorError(source_key, "invalid_payload", "Source returned an invalid payload"),
                http_status=connector.last_diagnostics.http_status,
            )
        except Exception:  # Connector bugs remain isolated and stack traces stay server-side.
            return ConnectorRun(
                source_key,
                [],
                (perf_counter() - started) * 1000,
                ConnectorError(source_key, "connector_error", "Connector could not complete"),
            )

    def _ensure_source(self, connector: BaseConnector) -> Source:
        cached = self._source_cache.get(connector.metadata.key)
        if cached is not None:
            return cached
        source = self.db.scalar(select(Source).where(Source.key == connector.metadata.key))
        configured, detail = connector.validate_configuration()
        if source is None:
            source = Source(
                key=connector.metadata.key,
                name=connector.metadata.name,
                kind=connector.metadata.kind,
                configured=configured,
                confidence=connector.metadata.confidence,
                config_public={
                    "detail": detail,
                    "requires_credentials": connector.metadata.requires_credentials,
                    "category": connector.metadata.category,
                    "support_level": connector.metadata.support_level,
                    "coverage_label": connector.metadata.coverage_label,
                    "capabilities": connector.metadata.capabilities.as_dict(),
                    "configuration_state": connector.configuration_state(),
                    "active_acquisition_mode": connector.active_acquisition_mode(),
                },
            )
            self.db.add(source)
            self.db.flush()
        else:
            source.configured = configured
            source.config_public = {
                "detail": detail,
                "requires_credentials": connector.metadata.requires_credentials,
                "category": connector.metadata.category,
                "support_level": connector.metadata.support_level,
                "coverage_label": connector.metadata.coverage_label,
                "capabilities": connector.metadata.capabilities.as_dict(),
                "configuration_state": connector.configuration_state(),
                "active_acquisition_mode": connector.active_acquisition_mode(),
            }
        if connector.metadata.key == "github":
            source.config_public = {
                **source.config_public,
                "scopes": list(getattr(connector, "scopes", ("repositories",))),
            }
        self._source_cache[connector.metadata.key] = source
        return source

    def _update_health(self, runs: list[ConnectorRun]) -> None:
        now = datetime.now(UTC)
        for run in runs:
            connector = self.connectors.get(run.source)
            if connector is None:
                continue
            source = self._ensure_source(connector)
            health = self.db.scalar(select(SourceHealth).where(SourceHealth.source_id == source.id))
            if health is None:
                health = SourceHealth(source_id=source.id)
                self.db.add(health)
            previous_requests = health.request_count or 0
            health.request_count = previous_requests + 1
            health.average_latency_ms = (
                (health.average_latency_ms or 0) * previous_requests + run.latency_ms
            ) / health.request_count
            health.last_checked_at = now
            health.last_latency_ms = run.latency_ms
            health.last_result_count = run.raw_result_count
            health.last_normalized_count = run.normalized_result_count
            health.last_malformed_count = run.malformed_count
            health.http_status = run.http_status
            if run.error:
                health.status = self._health_state(
                    run.error, partial_success=bool(run.items)
                )
                if run.items:
                    health.last_success_at = now
                health.failure_count = (health.failure_count or 0) + 1
                health.recent_failure = run.error.message
                health.failure_category = run.error.code
            else:
                recovered = health.status not in ("healthy", "unknown", "unconfigured")
                health.status = "healthy"
                health.last_success_at = now
                health.recent_failure = None
                health.failure_category = None
                if recovered:
                    self.db.add(
                        AuditEvent(
                            event_type="connector_recovered",
                            message="Connector recovered",
                            context={"source": run.source},
                        )
                    )

    def _persist_connector_runs(self, session_id: str, runs: list[ConnectorRun]) -> None:
        completed = datetime.now(UTC)
        for run in runs:
            self.db.add(
                ConnectorRunRecord(
                    search_session_id=session_id,
                    source_key=run.source,
                    status=self._health_state(run.error, partial_success=bool(run.items)),
                    error_category=run.error.code if run.error else None,
                    http_status=run.http_status,
                    latency_ms=run.latency_ms,
                    raw_result_count=run.raw_result_count,
                    fetched_result_count=run.fetched_result_count,
                    schema_valid_count=run.schema_valid_count,
                    query_match_count=run.query_match_count,
                    time_eligible_count=run.time_eligible_count,
                    normalized_result_count=run.normalized_result_count,
                    malformed_count=run.malformed_count,
                    attempt_count=run.attempt_count,
                    attempt_latencies_ms=list(run.attempt_latencies_ms),
                    circuit_breaker_state=run.circuit_breaker_state,
                    completed_at=completed,
                )
            )

    @staticmethod
    def _search_outcome(
        *,
        request: SearchRequest,
        planned_sources: list[str],
        runs: list[ConnectorRun],
        result_count: int,
    ) -> dict[str, Any]:
        completed = sorted({run.source for run in runs if run.error is None})
        partial = sorted({run.source for run in runs if run.error is not None and run.items})
        failed = sorted({run.source for run in runs if run.error is not None and not run.items})
        external_codes = {
            "access_limited",
            "auth_required",
            "captcha_blocked",
            "circuit_open",
            "dns_network",
            "http_403",
            "quota_exhausted",
            "rate_limited",
            "timeout",
            "upstream_5xx",
            "upstream_engines_unavailable",
        }
        external = sorted(
            {run.source for run in runs if run.error and run.error.code in external_codes}
        )
        time_filtered = sorted(
            {
                run.source
                for run in runs
                if run.query_match_count > run.time_eligible_count
            }
        )
        reason: str | None = None
        cause: str | None = None
        if result_count:
            reason = "RESULTS_AVAILABLE"
        elif not planned_sources or not runs:
            reason = "NO_CAPABLE_SOURCE"
        elif request.time_range.value != "all" and time_filtered:
            reason = "NO_MATCHES_IN_TIME_RANGE"
        elif failed and len(failed) == len({run.source for run in runs}):
            web_sources = {"x", "threads", "reddit"}
            if set(failed).issubset(web_sources) and all(
                run.error and run.error.code in {"unconfigured", "configuration_missing"}
                for run in runs
            ):
                reason = "WEB_DISCOVERY_BLOCKED"
            else:
                reason = "ALL_SELECTED_SOURCES_FAILED"
                cause = "EXTERNAL_LIMIT" if set(failed).issubset(external) else "SOURCE_UNAVAILABLE"
        else:
            reason = "NO_MATCHES"
        return {
            "reason": reason,
            "cause": cause,
            "time_range": request.time_range.value,
            "completed_sources": completed,
            "partial_sources": partial,
            "failed_sources": failed,
            "external_limit_sources": external,
            "time_filtered_sources": time_filtered,
        }

    @staticmethod
    def _health_state(
        error: ConnectorError | None, *, partial_success: bool = False
    ) -> str:
        if error is None:
            return "healthy"
        if partial_success:
            return "degraded"
        if error.code in {"unconfigured", "configuration_missing"}:
            return "unconfigured"
        if error.code in {"restricted_access", "capability_restricted"}:
            return "restricted"
        if error.code == "access_limited":
            return "access_limited"
        if error.code == "auth_required":
            return "auth_required"
        if error.code == "quota_exhausted":
            return "quota_exhausted"
        if error.code == "disabled":
            return "disabled"
        if error.code == "rate_limited":
            return "rate_limited"
        if error.code == "http_403":
            return "external_limit"
        if error.code in {"http_401", "http_404", "dns_network"}:
            return "unavailable"
        return "degraded"

    @staticmethod
    def _score_distributions(scores: dict[int, ScoreComponents]) -> dict[str, dict[str, int]]:
        fields = (
            "final_score",
            "relevance",
            "freshness",
            "engagement",
            "source_confidence",
            "cross_source_presence",
            "novelty",
        )
        output: dict[str, dict[str, int]] = {}
        for field in fields:
            buckets = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
            for score in scores.values():
                value = float(getattr(score, field))
                start = min(80, int(value // 20) * 20)
                label = "80-100" if start == 80 else f"{start}-{start + 19}"
                buckets[label] += 1
            output[field] = buckets
        return output

    @staticmethod
    def _source_relevance_distributions(
        persisted: list[tuple[ContentItem, str]], scores: dict[int, ScoreComponents]
    ) -> dict[str, dict[str, float | int]]:
        by_source: dict[str, list[float]] = {}
        for item, source in persisted:
            by_source.setdefault(source, []).append(scores[item.id].relevance)
        output: dict[str, dict[str, float | int]] = {}
        for source, raw_values in sorted(by_source.items()):
            values = sorted(raw_values)
            count = len(values)

            def percentile(
                fraction: float,
                *,
                sample: list[float] = values,
                sample_count: int = count,
            ) -> float:
                if sample_count == 1:
                    return sample[0]
                position = fraction * (sample_count - 1)
                lower = int(position)
                upper = min(sample_count - 1, lower + 1)
                weight = position - lower
                return sample[lower] * (1 - weight) + sample[upper] * weight

            output[source] = {
                "count": count,
                "min": round(values[0], 3),
                "p25": round(percentile(0.25), 3),
                "median": round(percentile(0.5), 3),
                "mean": round(sum(values) / count, 3),
                "p75": round(percentile(0.75), 3),
                "max": round(values[-1], 3),
            }
        return output

    def _persist_item(self, connector_item: ConnectorItem) -> tuple[ContentItem, str]:
        connector = self.connectors[connector_item.source]
        source = self._ensure_source(connector)
        item = self.db.scalar(
            select(ContentItem).where(
                ContentItem.source_id == source.id,
                ContentItem.external_id == connector_item.external_id,
            )
        )
        if item is None:
            raw_metadata = {
                **connector_item.raw_metadata,
                "acquisition_mode": connector_item.acquisition_mode.value,
                "acquisition_modes_seen": [connector_item.acquisition_mode.value],
            }
            item = ContentItem(
                source_id=source.id,
                external_id=connector_item.external_id,
                canonical_url=canonicalize_url(connector_item.canonical_url),
                author=connector_item.author,
                author_handle=connector_item.author_handle,
                author_verified=connector_item.author_verified,
                title=connector_item.title,
                text=connector_item.text,
                published_at=connector_item.published_at,
                fetched_at=connector_item.fetched_at,
                language=connector_item.language,
                hashtags=list(connector_item.hashtags)
                if connector_item.hashtags is not None
                else None,
                mentions=list(connector_item.mentions)
                if connector_item.mentions is not None
                else None,
                media_type=connector_item.media_type,
                acquisition_mode=connector_item.acquisition_mode.value,
                content_fingerprint=content_fingerprint(connector_item.title, connector_item.text),
                raw_metadata=raw_metadata,
                normalized_title=normalize_text(connector_item.title or ""),
                normalized_text=normalize_text(connector_item.text),
                normalized_author=normalize_text(connector_item.author or ""),
            )
            self.db.add(item)
            self.db.flush()
        else:
            previous_mode = item.acquisition_mode
            item.author_handle = connector_item.author_handle
            item.author_verified = connector_item.author_verified
            item.hashtags = (
                list(connector_item.hashtags) if connector_item.hashtags is not None else None
            )
            item.mentions = (
                list(connector_item.mentions) if connector_item.mentions is not None else None
            )
            item.media_type = connector_item.media_type
            item.acquisition_mode = connector_item.acquisition_mode.value
            previous_modes = list((item.raw_metadata or {}).get("acquisition_modes_seen") or ())
            modes = list(
                dict.fromkeys(
                    [*previous_modes, previous_mode, connector_item.acquisition_mode.value]
                )
            )
            item.raw_metadata = {
                **connector_item.raw_metadata,
                "acquisition_mode": connector_item.acquisition_mode.value,
                "acquisition_modes_seen": modes,
            }
            item.fetched_at = connector_item.fetched_at
            item.language = connector_item.language
            item.normalized_title = normalize_text(item.title or "")
            item.normalized_text = normalize_text(item.text)
            item.normalized_author = normalize_text(item.author or "")
        metric = self.db.scalar(
            select(ContentMetric).where(ContentMetric.content_item_id == item.id)
        )
        engagement = normalize_engagement(connector_item.source, connector_item.raw_metrics)
        metric_values = self._metric_values(connector_item.raw_metrics)
        if metric is None:
            self.db.add(
                ContentMetric(
                    content_item_id=item.id,
                    raw_metrics=connector_item.raw_metrics,
                    normalized_engagement=engagement,
                    **metric_values,
                )
            )
        else:
            metric.raw_metrics = connector_item.raw_metrics
            metric.normalized_engagement = engagement
            for name, value in metric_values.items():
                setattr(metric, name, value)
        return item, connector_item.source

    def _bm25_scores(self, query: ProcessedQuery, item_ids: list[int]) -> dict[int, float]:
        if not item_ids or not query.tokens:
            return {}
        id_parameters = {f"item_{index}": item_id for index, item_id in enumerate(item_ids)}
        placeholders = ", ".join(f":item_{index}" for index in range(len(item_ids)))
        rows = self.db.execute(
            text(
                "SELECT rowid, bm25(content_fts, 4.0, 1.0, 0.5, 4.0, 1.0, 0.5) AS score "
                "FROM content_fts WHERE content_fts MATCH :query "
                f"AND rowid IN ({placeholders})"
            ),
            {"query": fts_query(query), **id_parameters},
        ).all()
        strengths = {
            int(row.rowid): max(0.0, -float(row.score)) for row in rows if row.rowid in item_ids
        }
        maximum = max(strengths.values(), default=0)
        if maximum <= 0:
            return {item_id: 0 for item_id in item_ids}
        return {
            item_id: round(100 * strengths.get(item_id, 0) / maximum, 2) for item_id in item_ids
        }

    def _persist_duplicate_groups(
        self,
        session_id: str,
        groups,
        persisted: list[tuple[ContentItem, str]],
    ) -> tuple[dict[int, str], dict[int, float], dict[int, dict[str, int]]]:
        by_id = {item.id: item for item, _ in persisted}
        source_by_id = {item.id: source for item, source in persisted}
        group_by_item: dict[int, str] = {}
        cross_by_item: dict[int, float] = {}
        meta: dict[int, dict[str, int]] = {}
        for group in groups:
            canonical = max(
                group.members,
                key=lambda key: (
                    by_id[key].published_at.timestamp()
                    if by_id[key].published_at
                    else float("-inf"),
                    source_by_id[key],
                    by_id[key].external_id,
                ),
            )
            row = DuplicateGroup(
                search_session_id=session_id,
                canonical_item_id=canonical,
                source_count=len(group.sources),
                source_names=list(group.sources),
                record_count=len(group.members),
                earliest_seen=group.earliest_seen,
                latest_seen=group.latest_seen,
            )
            self.db.add(row)
            self.db.flush()
            for item_id in group.members:
                group_by_item[item_id] = row.id
                cross_by_item[item_id] = cross_source_score(len(group.sources))
                meta[item_id] = {
                    "canonical": canonical,
                    "count": len(group.members),
                    "source_count": len(group.sources),
                }
                self.db.add(
                    DuplicateGroupMember(
                        duplicate_group_id=row.id,
                        content_item_id=item_id,
                        similarity=group.similarities[item_id],
                        match_stage=group.stages[item_id],
                    )
                )
        return group_by_item, cross_by_item, meta

    def _persist_clusters(self, session_id: str, clusters, scores: dict[int, ScoreComponents]):
        cluster_by_item: dict[int, str] = {}
        cluster_sizes: list[int] = []
        for topic in clusters:
            aggregate = sum(scores[item_id].final_score for item_id in topic.members) / len(
                topic.members
            )
            row = Cluster(
                search_session_id=session_id,
                representative_title=topic.representative_title,
                member_count=len(topic.members),
                source_distribution=topic.source_distribution,
                platform_diversity=len(topic.source_distribution),
                earliest_at=topic.earliest_at,
                latest_at=topic.latest_at,
                aggregate_score=round(aggregate, 2),
                terms=list(topic.terms),
            )
            self.db.add(row)
            self.db.flush()
            cluster_sizes.append(len(topic.members))
            for item_id in topic.members:
                cluster_by_item[item_id] = row.id
                self.db.add(
                    ClusterMember(
                        cluster_id=row.id,
                        content_item_id=item_id,
                        similarity=topic.member_similarities.get(item_id, 1.0),
                    )
                )
        return cluster_by_item, cluster_sizes

    @staticmethod
    def _metric_values(metrics: dict[str, object]) -> dict[str, int | None]:
        mappings = {
            "like_count": "likes",
            "view_count": "views",
            "comment_count": "comments",
            "share_count": "shares",
            "repost_count": "reposts",
            "reaction_count": "reactions",
        }
        return {
            column: int(metrics[key])
            if isinstance(metrics.get(key), (int, float)) and not isinstance(metrics.get(key), bool)
            else None
            for column, key in mappings.items()
        }

    @staticmethod
    def _secondary_variants(
        lattice: QueryLattice, *, round_number: int
    ) -> tuple[QueryVariant, ...]:
        if round_number <= 1:
            return ()
        if round_number == 2:
            allowed = {
                QueryVariantType.EXACT,
                QueryVariantType.ARABIC_NORMALIZED,
                QueryVariantType.TRANSLITERATION,
                QueryVariantType.ENTITY_ALIAS,
            }
            values = [
                item
                for item in lattice.variants
                if item.transformation in allowed and item.drift_risk <= 0.35
            ]
        else:
            values = [
                item
                for item in lattice.variants
                if item.round_created == round_number
                and item.transformation == QueryVariantType.EVIDENCE_EXPANDED
                and item.drift_risk <= 0.35
            ]
        root_text = lattice.original.text.casefold().strip('"')
        return tuple(
            item
            for item in values
            if (
                item.text != lattice.original.text
                if item.transformation == QueryVariantType.EXACT
                else item.text.casefold().strip('"') != root_text
            )
        )

    @classmethod
    def _variants_for_connector_attempt(
        cls,
        lattice: QueryLattice,
        *,
        round_number: int,
        first_attempt: bool,
        web_index: bool,
    ) -> tuple[QueryVariant, ...]:
        if first_attempt and web_index:
            values = tuple(
                item
                for item in lattice.variants
                if item.round_created <= round_number and item.drift_risk <= 0.35
            )
            return values or (lattice.original,)
        if first_attempt:
            return (lattice.original,)
        values = cls._secondary_variants(lattice, round_number=round_number)
        if web_index:
            values = tuple(item for item in values if item.round_created == round_number)
        return values[:3] or (lattice.original,)

    @staticmethod
    def _matches_filters(item: ConnectorItem, request: SearchRequest) -> bool:
        source_type = str(item.raw_metadata.get("source_type", "record"))
        type_map = {
            "post": "posts",
            "video": "videos",
            "channel": "channels",
            "thread": "threads",
            "issue": "issues",
            "pull_request": "issues",
            "news": "news",
            "article": "news",
        }
        if (
            request.content_types
            and type_map.get(source_type, source_type) not in request.content_types
        ):
            return False
        has_media = bool(item.media_type and item.media_type not in {"post", "text", "record"})
        if request.has_media is not None and has_media is not request.has_media:
            return False
        has_links = (
            "http://" in item.text
            or "https://" in item.text
            or bool(item.raw_metadata.get("link_attachment_url"))
        )
        if request.has_links is not None and has_links is not request.has_links:
            return False
        if request.hashtags:
            tags = {tag.casefold() for tag in item.hashtags or ()}
            if not tags.intersection(tag.casefold() for tag in request.hashtags):
                return False
        return True

    @staticmethod
    def _matches_lattice(item: ConnectorItem, lattice: QueryLattice) -> bool:
        transformations = {variant.transformation for variant in lattice.variants}
        identifier_only_lane = (
            QueryVariantType.IDENTIFIER in transformations
            and QueryVariantType.HANDLE not in transformations
            and QueryVariantType.HASHTAG not in transformations
        )
        if identifier_only_lane:
            evidence = unicodedata.normalize(
                "NFKC",
                " ".join(
                    (
                        item.title or "",
                        item.text,
                        item.canonical_url,
                        item.author_handle or "",
                        " ".join(item.hashtags or ()),
                    )
                ),
            ).casefold()
            identifiers = {
                re.sub(r"\s+", " ", variant.text.strip().strip('"')).casefold()
                for variant in lattice.variants
                if variant.transformation == QueryVariantType.IDENTIFIER
            }
            return any(identifier and identifier in evidence for identifier in identifiers)
        for variant in lattice.variants:
            if variant.drift_risk > 0.35:
                continue
            query = process_query(
                variant.text,
                exact_phrase=variant.transformation.value == "EXACT",
            )
            if is_candidate_match(
                query,
                item.title,
                item.text,
                canonical_url=item.canonical_url,
                author_handle=item.author_handle,
                hashtags=item.hashtags,
            ):
                return True
        return False

    @classmethod
    def _planning_candidate_evidence(
        cls, items: list[ConnectorItem], lattice: QueryLattice
    ) -> list[CandidateEvidence]:
        output: list[CandidateEvidence] = []
        seen: set[str] = set()
        for item in items:
            canonical = canonicalize_url(item.canonical_url)
            if canonical in seen or not cls._matches_lattice(item, lattice):
                continue
            seen.add(canonical)
            completeness = evidence_completeness(item)
            output.append(
                CandidateEvidence(
                    canonical,
                    item.source,
                    completeness.score,
                    tuple(
                        str(value)
                        for value in item.raw_metadata.get("query_variants_that_found_it", ())
                    ),
                    tuple(
                        str(value) for value in item.raw_metadata.get("engines_that_found_it", ())
                    ),
                )
            )
        return output

    def _observe_alias_evidence(self, planning, items: list[ConnectorItem]) -> int:
        if not (
            planning.fingerprint.has(IntentLabel.PERSON_LIKE)
            or planning.fingerprint.has(IntentLabel.ENTITY_LIKE)
        ):
            return 0
        repository = EntityAliasRepository(self.db)
        observed = 0
        query_name = normalize_text(planning.fingerprint.original)
        for item in items:
            if not item.author_handle or normalize_text(item.author or "") != query_name:
                continue
            edge = repository.observe(
                planning.fingerprint.original,
                item.author_handle,
                relationship_type="name_to_handle",
                evidence_source=item.source,
                direct_evidence=True,
            )
            observed += int(edge is not None)
        return observed

    @staticmethod
    def _within_time_range(published_at: datetime | None, since: datetime | None) -> bool:
        if since is None or published_at is None:
            return True
        aware = published_at.replace(tzinfo=UTC) if published_at.tzinfo is None else published_at
        return aware.astimezone(UTC) >= since

    @staticmethod
    def _candidate_order_key(query: ProcessedQuery, item: ConnectorItem):
        relevance, _ = relevance_score(
            query,
            item.title,
            item.text,
            bm25_normalized=0,
            canonical_url=item.canonical_url,
            author_handle=item.author_handle,
            hashtags=item.hashtags,
        )
        published = item.published_at
        if published is not None:
            published = published.replace(tzinfo=UTC) if published.tzinfo is None else published
            published_key = published.astimezone(UTC).timestamp()
        else:
            published_key = float("-inf")
        return relevance, published_key, item.source, item.external_id

    def _ranking_weights(self) -> dict[str, float]:
        mapping = {
            "relevance": "ranking.relevance",
            "freshness": "ranking.freshness",
            "engagement": "ranking.engagement",
            "source_confidence": "ranking.source_confidence",
            "cross_source_presence": "ranking.cross_source_presence",
            "novelty": "ranking.novelty",
        }
        persisted = {
            row.key: float(row.value)
            for row in self.db.scalars(
                select(Setting).where(Setting.key.in_(mapping.values()))
            ).all()
        }
        weights = {
            signal: persisted.get(setting_key, self.settings.ranking_weights[signal])
            for signal, setting_key in mapping.items()
        }
        if abs(sum(weights.values()) - 1.0) > 1e-6:
            return self.settings.ranking_weights
        return weights

    @staticmethod
    def _sort_items(
        persisted,
        scores,
        sort_mode: SortMode,
        *,
        semantic_candidate_ids: set[int] | None = None,
        duplicate_meta: dict[int, dict[str, int]] | None = None,
    ):
        semantic_candidate_ids = semantic_candidate_ids or set()
        duplicate_meta = duplicate_meta or {}

        def sort_key(pair):
            published = pair[0].published_at.timestamp() if pair[0].published_at else float("-inf")
            stable_id = f"{pair[1]}:{pair[0].external_id}"
            if sort_mode == SortMode.NEWEST:
                return (published, scores[pair[0].id].final_score, stable_id)
            if sort_mode == SortMode.MOST_ENGAGED:
                return (
                    scores[pair[0].id].engagement,
                    scores[pair[0].id].final_score,
                    published,
                    stable_id,
                )
            if sort_mode == SortMode.CROSS_PLATFORM:
                return (
                    scores[pair[0].id].cross_source_presence,
                    scores[pair[0].id].final_score,
                    published,
                    stable_id,
                )
            duplicate = duplicate_meta.get(pair[0].id)
            representative = not duplicate or duplicate.get("canonical") == pair[0].id
            return (
                representative,
                pair[0].id in semantic_candidate_ids,
                scores[pair[0].id].final_score,
                scores[pair[0].id].lexical_relevance,
                published,
                stable_id,
            )

        return sorted(persisted, key=sort_key, reverse=True)

    @staticmethod
    def _lexical_ranking_key(
        query: ProcessedQuery,
        item: ContentItem,
        bm25_normalized: float,
        source: str,
    ) -> tuple[float, float, float, str]:
        relevance, _ = relevance_score(
            query,
            item.title,
            item.text,
            bm25_normalized=bm25_normalized,
            canonical_url=item.canonical_url,
            author_handle=item.author_handle,
            hashtags=item.hashtags,
        )
        published = item.published_at.timestamp() if item.published_at else float("-inf")
        return relevance, bm25_normalized, published, f"{source}:{item.external_id}"

    @staticmethod
    def _select_semantic_candidates(
        lexical_candidates: list[tuple[ContentItem, str]],
        limit: int,
    ) -> list[tuple[ContentItem, str]]:
        """Bound expensive evaluation without favoring a source's volume or arrival order."""
        if limit <= 0 or not lexical_candidates:
            return []
        queues: dict[str, list[tuple[ContentItem, str]]] = {}
        source_order: list[str] = []
        for candidate in lexical_candidates:
            source = candidate[1]
            if source not in queues:
                queues[source] = []
                source_order.append(source)
            queues[source].append(candidate)
        selected: list[tuple[ContentItem, str]] = []
        position = 0
        while len(selected) < limit:
            added = False
            for source in source_order:
                queue = queues[source]
                if position < len(queue):
                    selected.append(queue[position])
                    added = True
                    if len(selected) >= limit:
                        break
            if not added:
                break
            position += 1
        return selected

    @staticmethod
    def _semantic_diagnostics(semantic: SemanticScores) -> dict[str, object]:
        return {
            "strategy": (
                "lexical_candidate_semantic_rerank"
                if semantic.state == "ready"
                else "lexical_explainable"
            ),
            "semantic_state": semantic.state,
            "semantic_model": semantic.model,
            "semantic_model_version": semantic.model_version,
            "semantic_query_type": semantic.query_type,
            "semantic_duration_ms": semantic.duration_ms,
            "semantic_candidate_count": len(semantic.scores),
            "embedding_cache_hits": semantic.cache_hits,
            "embedding_cache_misses": semantic.cache_misses,
            "semantic_timings_ms": semantic.timings_ms,
            "embedding_batch_size": semantic.batch_size,
            "detail": semantic.detail,
        }
