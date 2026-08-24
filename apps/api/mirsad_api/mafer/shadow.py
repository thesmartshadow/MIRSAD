from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .learning import LearnedUtility
from .routing import ResourcePlan, ResourceUtility
from .versions import SHADOW_ROUTER_VERSION


@dataclass(frozen=True, slots=True)
class ShadowRoutePlan:
    ordered_sources: tuple[str, ...]
    production_sources: tuple[str, ...]
    adjustments: dict[str, float]
    recommended_sources: tuple[str, ...]
    deferred_sources: tuple[str, ...]
    decisions: dict[str, dict[str, Any]]
    changed: bool
    version: str = SHADOW_ROUTER_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "production_sources": list(self.production_sources),
            "ordered_sources": list(self.ordered_sources),
            "adjustments": self.adjustments,
            "recommended_sources": list(self.recommended_sources),
            "deferred_sources": list(self.deferred_sources),
            "decisions": self.decisions,
            "changed": self.changed,
            "mode": "SHADOW_ONLY",
        }


def shadow_route(
    production: ResourcePlan,
    *,
    query_class: str,
    learned: dict[tuple[str, str], LearnedUtility],
) -> ShadowRoutePlan:
    production_sources = tuple(item.source for item in production.ordered)

    def adjusted(item: ResourceUtility) -> tuple[float, str]:
        observation = learned.get((query_class, item.source))
        adjustment = observation.adjustment if observation else 0.0
        return (item.total + adjustment, item.source)

    ordered = tuple(
        item.source
        for item in sorted(production.ordered, key=lambda item: (-adjusted(item)[0], item.source))
    )
    adjustments = {
        source: learned[(query_class, source)].adjustment
        for source in production_sources
        if (query_class, source) in learned
    }
    ordered_items = sorted(production.ordered, key=lambda item: (-adjusted(item)[0], item.source))
    minimum_by_class = {
        "identifier": 4,
        "handle": 4,
        "hashtag": 4,
        "exact_phrase": 4,
        "person_like": 4,
        "person": 4,
        "entity_like": 4,
        "entity": 4,
        "historical_intent": 4,
        "historical": 4,
        "topic": 4,
        "arabic_topic": 4,
        "english_topic": 4,
        "recent": 4,
    }
    minimum = min(len(ordered_items), minimum_by_class.get(query_class, len(ordered_items)))
    recommended: list[str] = []
    deferred: list[str] = []
    decisions: dict[str, dict[str, Any]] = {}
    best_score = adjusted(ordered_items[0])[0] if ordered_items else 0.0
    for index, item in enumerate(ordered_items):
        observation = learned.get((query_class, item.source))
        score = adjusted(item)[0]
        enough_evidence = bool(observation and observation.observations >= 5)
        weak_observed_utility = bool(observation and observation.adjustment <= -1.5)
        protected = index < minimum or item.capability_match >= 90.0
        keep = item.available and (
            protected
            or not enough_evidence
            or not weak_observed_utility
            or score >= best_score - 18.0
        )
        if keep:
            recommended.append(item.source)
            reason = (
                "protected query-class capability"
                if protected
                else "insufficient evidence to defer"
                if not enough_evidence
                else "expected evidence gain remains competitive"
            )
        else:
            deferred.append(item.source)
            reason = (
                "currently unavailable; long-term utility retained"
                if not item.available
                else "repeated low observed yield relative to expected retrieval cost"
            )
        decisions[item.source] = {
            "recommendation": "SELECT" if keep else "DEFER",
            "reason": reason,
            "expected_utility": round(score, 3),
            "long_term_utility": round(item.long_term_utility, 3),
            "current_availability": round(item.current_availability, 3),
            "observations": observation.observations if observation else 0,
        }
    return ShadowRoutePlan(
        ordered,
        production_sources,
        adjustments,
        tuple(recommended),
        tuple(deferred),
        decisions,
        ordered != production_sources or tuple(recommended) != production_sources,
    )
