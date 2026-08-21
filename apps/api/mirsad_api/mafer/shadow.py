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
    changed: bool
    version: str = SHADOW_ROUTER_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "production_sources": list(self.production_sources),
            "ordered_sources": list(self.ordered_sources),
            "adjustments": self.adjustments,
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
    return ShadowRoutePlan(
        ordered,
        production_sources,
        adjustments,
        ordered != production_sources,
    )
