from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .assessment import UncertaintyLevel
from .intent import IntentLabel, QueryIntentFingerprint
from .versions import SHADOW_STOP_MODEL_VERSION, SHADOW_UNCERTAINTY_VERSION


@dataclass(frozen=True, slots=True)
class ObservableSearchEvidence:
    candidate_count: int
    source_count: int
    healthy_unqueried_sources: int
    variant_agreement: float
    lexical_semantic_disagreement: float
    rank_margin: float
    evidence_completeness: float
    single_engine_dependence: bool
    degraded_sources: int = 0
    round_number: int = 1
    previous_unique_gain: int | None = None
    current_unique_gain: int = 0
    previous_admitted_gain: int | None = None
    current_admitted_gain: int = 0


@dataclass(frozen=True, slots=True)
class CalibratedUncertainty:
    level: UncertaintyLevel
    risk_points: int
    reasons: tuple[str, ...]
    version: str = SHADOW_UNCERTAINTY_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "risk_points": self.risk_points,
            "reasons": list(self.reasons),
            "version": self.version,
        }


class SaturationDecision(StrEnum):
    CONTINUE = "CONTINUE"
    STOP = "STOP"


@dataclass(frozen=True, slots=True)
class SearchSaturation:
    decision: SaturationDecision
    reason: str
    evidence: tuple[str, ...]
    version: str = SHADOW_STOP_MODEL_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "version": self.version,
        }


def calibrated_uncertainty(
    evidence: ObservableSearchEvidence,
    *,
    fingerprint: QueryIntentFingerprint | None = None,
) -> CalibratedUncertainty:
    """Development-calibrated shadow assessment; it never controls production search."""

    risk = 0
    reasons: list[str] = []
    if evidence.candidate_count < 5:
        risk += 2
        reasons.append("very few candidates")
    elif evidence.candidate_count < 10:
        risk += 1
        reasons.append("limited candidate yield")
    if evidence.source_count <= 1:
        risk += 2
        reasons.append("single-source evidence")
    elif evidence.source_count == 2:
        risk += 1
        reasons.append("only two independent sources")
    if evidence.evidence_completeness < 0.45:
        risk += 2
        reasons.append("evidence completeness is low")
    elif evidence.evidence_completeness < 0.65:
        risk += 1
        reasons.append("evidence completeness is moderate")
    if evidence.variant_agreement < 0.35:
        risk += 2
        reasons.append("query variants disagree")
    elif evidence.variant_agreement < 0.60:
        risk += 1
        reasons.append("query-variant agreement is limited")
    if evidence.lexical_semantic_disagreement > 30:
        risk += 2
        reasons.append("large lexical/semantic disagreement")
    elif evidence.lexical_semantic_disagreement > 20:
        risk += 1
        reasons.append("moderate lexical/semantic disagreement")
    if evidence.rank_margin < 3:
        risk += 2
        reasons.append("top-rank margin is unstable")
    elif evidence.rank_margin < 8:
        risk += 1
        reasons.append("top-rank margin is narrow")
    if evidence.healthy_unqueried_sources >= 3:
        risk += 2
        reasons.append("several healthy useful sources remain unqueried")
    elif evidence.healthy_unqueried_sources:
        risk += 1
        reasons.append("healthy useful sources remain unqueried")
    if evidence.single_engine_dependence:
        risk += 1
        reasons.append("single discovery-engine dependence")
    if evidence.degraded_sources:
        risk += 1
        reasons.append("queried source paths degraded")
    difficult_identity = bool(
        fingerprint
        and fingerprint.has(IntentLabel.ARABIC)
        and any(
            fingerprint.has(label)
            for label in (
                IntentLabel.PERSON_LIKE,
                IntentLabel.ENTITY_LIKE,
                IntentLabel.EXACT_PHRASE,
            )
        )
    )
    if difficult_identity and evidence.healthy_unqueried_sources:
        risk += 1
        reasons.append("Arabic identity/exact intent still has unqueried coverage")
    if evidence.round_number > 1 and evidence.previous_unique_gain is not None:
        unique_ratio = evidence.current_unique_gain / max(1, evidence.previous_unique_gain)
        admitted_ratio = evidence.current_admitted_gain / max(
            1, evidence.previous_admitted_gain or evidence.previous_unique_gain
        )
        if unique_ratio < 0.15 and admitted_ratio < 0.15:
            risk = max(0, risk - 2)
            reasons.append("round gain has saturated")
    if (
        evidence.source_count >= 4
        and evidence.candidate_count >= 15
        and evidence.evidence_completeness >= 0.70
        and evidence.variant_agreement >= 0.70
    ):
        risk = max(0, risk - 2)
        reasons.append("independent sources and coherent complete evidence")
    if evidence.healthy_unqueried_sources == 0:
        risk = max(0, risk - 1)
        reasons.append("no healthy useful source remains unqueried")

    level = (
        UncertaintyLevel.LOW
        if risk <= 1
        else UncertaintyLevel.MEDIUM
        if risk <= 4
        else UncertaintyLevel.HIGH
    )
    return CalibratedUncertainty(
        level,
        risk,
        tuple(dict.fromkeys(reasons)) or ("observable evidence is stable",),
    )


def saturation_decision(
    evidence: ObservableSearchEvidence,
    uncertainty: CalibratedUncertainty,
    *,
    elapsed_seconds: float,
    max_wall_clock_seconds: float,
    requests_used: int,
    max_requests: int,
    round_number: int,
    max_rounds: int,
) -> SearchSaturation:
    """Explainable shadow stop policy. Hard budgets always override adaptive evidence."""

    if elapsed_seconds >= max_wall_clock_seconds:
        return SearchSaturation(SaturationDecision.STOP, "TIME_BUDGET", ("wall-clock budget",))
    if requests_used >= max_requests:
        return SearchSaturation(SaturationDecision.STOP, "REQUEST_BUDGET", ("request budget",))
    if round_number >= max_rounds:
        return SearchSaturation(SaturationDecision.STOP, "MAX_ROUNDS", ("round budget",))
    if evidence.healthy_unqueried_sources == 0:
        return SearchSaturation(
            SaturationDecision.STOP,
            "SOURCE_EXHAUSTION",
            ("no healthy useful source remains",),
        )
    if evidence.round_number > 1 and evidence.previous_unique_gain is not None:
        unique_ratio = evidence.current_unique_gain / max(1, evidence.previous_unique_gain)
        admitted_ratio = evidence.current_admitted_gain / max(
            1, evidence.previous_admitted_gain or evidence.previous_unique_gain
        )
        if unique_ratio < 0.15 and admitted_ratio < 0.15:
            return SearchSaturation(
                SaturationDecision.STOP,
                "LOW_MARGINAL_GAIN",
                ("unique and admitted gain both below 15% of the previous round",),
            )
    if uncertainty.level in {UncertaintyLevel.MEDIUM, UncertaintyLevel.HIGH}:
        return SearchSaturation(
            SaturationDecision.CONTINUE,
            "UNCERTAINTY_WITH_AVAILABLE_COVERAGE",
            (
                f"{uncertainty.level.value.lower()} retrieval uncertainty",
                f"{evidence.healthy_unqueried_sources} healthy useful source(s) remain",
            ),
        )
    return SearchSaturation(
        SaturationDecision.STOP,
        "SATISFIED",
        ("low uncertainty", "additional source utility is not expected to justify its cost"),
    )
