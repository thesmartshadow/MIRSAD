from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..connectors.base import BaseConnector
from ..domains.query import ProcessedQuery
from ..models import ContentItem, Source, SourceHealth
from .aliases import EntityAliasRepository
from .budget import SearchBudget, SearchMode, budget_for
from .intent import IntentLabel, QueryIntentAnalyzer, QueryIntentFingerprint
from .lattice import QueryLattice, build_query_lattice
from .learning import ShadowUtilityLearner
from .memory import LocalMemoryResult, LocalMemorySearch
from .routing import ResourceObservation, ResourcePlan, ResourceRouter
from .shadow import ShadowRoutePlan, shadow_route
from .versions import production_versions, shadow_versions


@dataclass(frozen=True, slots=True)
class AdaptivePlanningContext:
    fingerprint: QueryIntentFingerprint
    lattice: QueryLattice
    budget: SearchBudget
    resources: ResourcePlan
    local_memory: LocalMemoryResult
    source_states: dict[str, str]
    shadow_resources: ShadowRoutePlan

    def initial_trace(self) -> dict[str, Any]:
        return {
            "intent_fingerprint": self.fingerprint.as_dict(),
            "temporal_intent": self.fingerprint.temporal_intent.value,
            "query_lattice": self.lattice.as_dict(),
            "budget": self.budget.as_dict(),
            "resource_plan": self.resources.as_dict(),
            "algorithm_versions": production_versions(),
            "shadow_versions": shadow_versions(),
            "shadow_router": self.shadow_resources.as_dict(),
            "rounds": [
                {
                    "round": 0,
                    "kind": "LOCAL_MEMORY",
                    **self.local_memory.as_dict(),
                    "current_coverage": False,
                    "reason": "local accelerator; not current platform coverage",
                }
            ],
        }


class AdaptiveSearchPlanner:
    def __init__(self, db: Session, connectors: Mapping[str, BaseConnector]) -> None:
        self.db = db
        self.connectors = connectors

    def prepare(
        self,
        processed: ProcessedQuery,
        *,
        selected_sources: list[str],
        source_selection: str,
        mode: SearchMode | str,
        explicit_time_range: str,
    ) -> AdaptivePlanningContext:
        budget = budget_for(mode)
        frequencies, document_count = self._token_frequencies(processed.tokens)
        fingerprint = QueryIntentAnalyzer().analyze(
            processed,
            token_document_frequency=frequencies,
            document_count=document_count,
            explicit_time_range=explicit_time_range,
        )
        alias_repository = EntityAliasRepository(self.db)
        aliases = tuple(
            (item.value, item.confidence)
            for item in alias_repository.aliases_for(processed.original)
        )
        lattice = build_query_lattice(
            processed,
            fingerprint,
            max_variants=budget.max_query_variants,
            aliases=aliases,
        )
        source_states, observations = self._source_observations()
        if source_selection == "auto":
            source_keys = [
                key for key in self.connectors if key != "mock" or key in selected_sources
            ]
        else:
            source_keys = selected_sources
        resources = ResourceRouter().route(
            fingerprint,
            self.connectors,
            source_keys,
            budget,
            explicit_selection=source_selection == "explicit",
            current_states=source_states,
            observations=observations,
        )
        local_memory = LocalMemorySearch(self.db).search(
            processed,
            lattice,
            limit=min(budget.max_normalized_candidates, 100),
        )
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
                if fingerprint.has(label)
            ),
            "unknown",
        )
        shadow_resources = shadow_route(
            resources,
            query_class=query_class,
            learned=ShadowUtilityLearner(self.db).source_utilities(),
        )
        return AdaptivePlanningContext(
            fingerprint,
            lattice,
            budget,
            resources,
            local_memory,
            source_states,
            shadow_resources,
        )

    def _token_frequencies(self, tokens: tuple[str, ...]) -> tuple[dict[str, int], int]:
        document_count = int(self.db.scalar(select(func.count(ContentItem.id))) or 0)
        frequencies: dict[str, int] = {}
        for token in tokens[:10]:
            try:
                frequencies[token] = int(
                    self.db.execute(
                        text("SELECT count(*) FROM content_fts WHERE content_fts MATCH :query"),
                        {"query": f'"{token.replace(chr(34), chr(34) * 2)}"'},
                    ).scalar_one()
                )
            except Exception:
                frequencies[token] = 0
        return frequencies, document_count

    def _source_observations(
        self,
    ) -> tuple[dict[str, str], dict[str, ResourceObservation]]:
        rows = self.db.execute(
            select(Source, SourceHealth).outerjoin(
                SourceHealth, SourceHealth.source_id == Source.id
            )
        ).all()
        states: dict[str, str] = {}
        observations: dict[str, ResourceObservation] = {}
        for source, health in rows:
            if health is None:
                continue
            states[source.key] = health.status
            raw = max(1, health.last_result_count)
            yield_rate = min(1.0, health.last_normalized_count / raw)
            observations[source.key] = ResourceObservation(
                historical_yield=yield_rate if health.request_count else 0.5,
                unique_yield=0.5,
                duplicate_rate=0.0,
                average_latency_ms=health.average_latency_ms,
            )
        return states, observations
