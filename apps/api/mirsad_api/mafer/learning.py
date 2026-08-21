from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ContentItem,
    SearchOutcomeEvent,
    SearchSession,
    ShadowEvaluation,
    SourceUtilityObservation,
)
from .versions import production_versions

OUTCOME_EVENTS = frozenset(
    {
        "SEARCH_EXECUTED",
        "RESULT_OPENED",
        "RESULT_BOOKMARKED",
        "RESULT_MARKED_RELEVANT",
        "RESULT_MARKED_NOT_RELEVANT",
        "SEARCH_REFORMULATED",
        "ZERO_RESULT",
        "SOURCE_FAILURE",
    }
)
EXPLICIT_EVENTS = {
    "RESULT_MARKED_RELEVANT": "relevant",
    "RESULT_MARKED_NOT_RELEVANT": "not_relevant",
}
QUERY_CLASS_PRIORITY = (
    "IDENTIFIER",
    "HANDLE",
    "HASHTAG",
    "EXACT_PHRASE",
    "PERSON_LIKE",
    "ENTITY_LIKE",
    "EVENT_LIKE",
    "HISTORICAL_INTENT",
    "TOPIC",
    "AMBIGUOUS",
)


def session_query_class(session: SearchSession) -> str:
    labels = (
        (session.diagnostics or {}).get("mafer", {}).get("intent_fingerprint", {}).get("labels", [])
    )
    return next((label.casefold() for label in QUERY_CLASS_PRIORITY if label in labels), "unknown")


class OutcomeRecorder:
    """Records local, bounded outcome evidence without interpreting clicks as relevance."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        event_type: str,
        *,
        session: SearchSession | None = None,
        item: ContentItem | None = None,
        rank: int | None = None,
        source: str | None = None,
        acquisition_mode: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> SearchOutcomeEvent:
        if event_type not in OUTCOME_EVENTS:
            raise ValueError("Unsupported search outcome event")
        if rank is not None and not 1 <= rank <= 10_000:
            raise ValueError("Result rank is outside the accepted range")
        safe_context = context or {}
        if len(str(safe_context)) > 4_000:
            raise ValueError("Outcome context is too large")
        versions = production_versions()
        if session:
            versions = {
                **versions,
                **((session.diagnostics or {}).get("mafer", {}).get("algorithm_versions", {})),
            }
        row = SearchOutcomeEvent(
            search_session_id=session.id if session else None,
            content_item_id=item.id if item else None,
            event_type=event_type,
            query_class=session_query_class(session) if session else "unknown",
            rank=rank,
            source=source,
            acquisition_mode=acquisition_mode or (item.acquisition_mode if item else None),
            explicit_judgment=EXPLICIT_EVENTS.get(event_type),
            algorithm_versions=versions,
            context=safe_context,
        )
        self.db.add(row)
        return row


@dataclass(frozen=True, slots=True)
class LearnedUtility:
    query_class: str
    source: str
    observations: int
    explicit_judgments: int
    adjustment: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_class": self.query_class,
            "source": self.source,
            "observations": self.observations,
            "explicit_judgments": self.explicit_judgments,
            "adjustment": self.adjustment,
            "reasons": list(self.reasons),
        }


class ShadowUtilityLearner:
    """Conservative retrieval-utility learner; output is shadow-only and bounded."""

    minimum_observations = 5
    maximum_adjustment = 8.0
    decay_half_life_days = 30.0

    def __init__(self, db: Session, *, now: datetime | None = None) -> None:
        self.db = db
        self.now = now or datetime.now(UTC)

    def source_utilities(self) -> dict[tuple[str, str], LearnedUtility]:
        observations = self.db.scalars(select(SourceUtilityObservation)).all()
        explicit_events = self.db.scalars(
            select(SearchOutcomeEvent).where(SearchOutcomeEvent.explicit_judgment.is_not(None))
        ).all()
        grouped: dict[tuple[str, str], list[SourceUtilityObservation]] = defaultdict(list)
        for row in observations:
            grouped[(row.query_class, row.source)].append(row)
        judgments: dict[tuple[str, str], list[SearchOutcomeEvent]] = defaultdict(list)
        for event in explicit_events:
            if event.source:
                judgments[(event.query_class, event.source)].append(event)
        output: dict[tuple[str, str], LearnedUtility] = {}
        for key, rows in grouped.items():
            reasons: list[str] = []
            if len(rows) < self.minimum_observations:
                output[key] = LearnedUtility(
                    *key, len(rows), len(judgments[key]), 0.0, ("minimum evidence not reached",)
                )
                continue
            weighted_total = 0.0
            weight_sum = 0.0
            for row in rows:
                age_days = max(0.0, (self.now - row.created_at).total_seconds() / 86_400)
                weight = math.pow(0.5, age_days / self.decay_half_life_days)
                returned = max(1, row.returned_count)
                yield_quality = min(1.0, row.admitted_count / returned)
                unique_quality = min(1.0, row.unique_count / returned)
                top_quality = min(1.0, row.top_k_count / max(1, row.admitted_count))
                latency_cost = min(1.0, row.latency_ms / 8_000)
                failure_cost = 1.0 if row.failure_category else 0.0
                score = (
                    0.35 * yield_quality
                    + 0.30 * unique_quality
                    + 0.20 * top_quality
                    - 0.10 * min(1.0, row.duplicate_rate)
                    - 0.03 * latency_cost
                    - 0.02 * failure_cost
                )
                weighted_total += weight * score
                weight_sum += weight
            centered = (weighted_total / max(weight_sum, 1e-9) - 0.35) * 10
            latest_by_item: dict[int, SearchOutcomeEvent] = {}
            for event in judgments[key]:
                if event.content_item_id is None:
                    continue
                current = latest_by_item.get(event.content_item_id)
                if current is None or current.created_at < event.created_at:
                    latest_by_item[event.content_item_id] = event
            explicit = list(latest_by_item.values())
            if len(explicit) >= 3:
                relevant = sum(event.explicit_judgment == "relevant" for event in explicit)
                centered += ((relevant / len(explicit)) - 0.5) * 4
                reasons.append("bounded explicit judgments included")
            elif explicit:
                reasons.append("explicit judgments below promotion evidence minimum")
            reasons.append("time-decayed retrieval yield, uniqueness, cost, and failures")
            adjustment = round(
                max(-self.maximum_adjustment, min(self.maximum_adjustment, centered)), 3
            )
            output[key] = LearnedUtility(*key, len(rows), len(explicit), adjustment, tuple(reasons))
        return output


def record_shadow_comparison(
    db: Session,
    *,
    session_id: str,
    strategy_type: str,
    strategy_version: str,
    production_output: dict[str, Any],
    shadow_output: dict[str, Any],
    comparison: dict[str, Any],
) -> None:
    db.add(
        ShadowEvaluation(
            search_session_id=session_id,
            strategy_type=strategy_type,
            strategy_version=strategy_version,
            production_output=production_output,
            shadow_output=shadow_output,
            comparison=comparison,
        )
    )
