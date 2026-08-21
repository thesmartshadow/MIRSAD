from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class UncertaintyLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class StopReason(StrEnum):
    SATISFIED = "SATISFIED"
    LOW_MARGINAL_GAIN = "LOW_MARGINAL_GAIN"
    MAX_ROUNDS = "MAX_ROUNDS"
    TIME_BUDGET = "TIME_BUDGET"
    REQUEST_BUDGET = "REQUEST_BUDGET"
    SOURCE_EXHAUSTION = "SOURCE_EXHAUSTION"
    NO_AVAILABLE_SOURCES = "NO_AVAILABLE_SOURCES"
    USER_LIMIT = "USER_LIMIT"


class RetrievalOutcome(StrEnum):
    RESULT = "RESULT"
    NO_RELEVANT_RESULT = "NO_RELEVANT_RESULT"
    DISCOVERY_EXTERNALLY_BLOCKED = "DISCOVERY_EXTERNALLY_BLOCKED"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    CONNECTOR_ERROR = "CONNECTOR_ERROR"


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    canonical_url: str
    source: str
    metadata_completeness: float
    variant_ids: tuple[str, ...] = ()
    engine_ids: tuple[str, ...] = ()
    lexical_strength: float | None = None
    semantic_strength: float | None = None


@dataclass(frozen=True, slots=True)
class SearchUncertainty:
    level: UncertaintyLevel
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"level": self.level.value, "reasons": list(self.reasons)}


@dataclass(frozen=True, slots=True)
class MarginalEvidenceGain:
    round_number: int
    new_canonical_urls: int
    new_admitted_candidates: int
    new_platforms: int
    new_stories: int
    new_aliases: int
    network_requests: int
    elapsed_ms: float
    gain: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "round": self.round_number,
            "new_canonical_urls": self.new_canonical_urls,
            "new_admitted_candidates": self.new_admitted_candidates,
            "new_platforms": self.new_platforms,
            "new_stories": self.new_stories,
            "new_aliases": self.new_aliases,
            "network_requests": self.network_requests,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "gain": round(self.gain, 3),
            "reasons": list(self.reasons),
        }


def assess_uncertainty(
    candidates: Iterable[CandidateEvidence],
    *,
    degraded_sources: int = 0,
    unqueried_useful_sources: int = 0,
) -> SearchUncertainty:
    values = list(candidates)
    reasons: list[str] = []
    if not values:
        return SearchUncertainty(
            UncertaintyLevel.HIGH,
            ("no candidate evidence",)
            + (("useful sources remain unqueried",) if unqueried_useful_sources else ()),
        )
    sources = {item.source for item in values}
    average_completeness = sum(item.metadata_completeness for item in values) / len(values)
    engine_support = set().union(*(set(item.engine_ids) for item in values))
    variant_support = set().union(*(set(item.variant_ids) for item in values))
    disagreements = [
        abs(item.lexical_strength - item.semantic_strength)
        for item in values
        if item.lexical_strength is not None and item.semantic_strength is not None
    ]
    average_disagreement = sum(disagreements) / len(disagreements) if disagreements else 0.0
    risk = 0
    if len(values) < 5:
        risk += 2
        reasons.append("few candidates")
    elif len(values) < 10:
        risk += 1
        reasons.append("limited candidate yield")
    if len(sources) == 1:
        risk += 1
        reasons.append("single-source dependence")
    if average_completeness < 0.35:
        risk += 2
        reasons.append("evidence is mostly URL/title/snippet only")
    elif average_completeness < 0.6:
        risk += 1
        reasons.append("metadata completeness is moderate")
    if len(engine_support) == 1 and any(item.engine_ids for item in values):
        risk += 1
        reasons.append("single discovery-engine dependence")
    if average_disagreement > 35:
        risk += 2
        reasons.append("large lexical/semantic disagreement")
    if degraded_sources:
        risk += 1
        reasons.append(f"{degraded_sources} queried source paths degraded")
    if len(variant_support) > 1:
        reasons.append("multiple query variants contributed evidence")
        risk = max(0, risk - 1)
    if len(sources) >= 3 and len(values) >= 10 and average_completeness >= 0.55:
        risk = max(0, risk - 2)
        reasons.append("multi-source yield with useful evidence completeness")
    if risk <= 1:
        level = UncertaintyLevel.LOW
    elif risk <= 3:
        level = UncertaintyLevel.MEDIUM
    else:
        level = UncertaintyLevel.HIGH
    return SearchUncertainty(level, tuple(dict.fromkeys(reasons)) or ("stable evidence",))


def marginal_evidence_gain(
    round_number: int,
    *,
    new_canonical_urls: int,
    new_admitted_candidates: int,
    new_platforms: int,
    new_stories: int = 0,
    new_aliases: int = 0,
    network_requests: int,
    elapsed_ms: float,
) -> MarginalEvidenceGain:
    useful = (
        new_canonical_urls
        + 1.5 * new_admitted_candidates
        + 2.0 * new_platforms
        + 1.5 * new_stories
        + new_aliases
    )
    cost = max(1.0, network_requests + elapsed_ms / 5000.0)
    gain = math.log1p(useful) / cost
    reasons: list[str] = []
    if new_canonical_urls == 0:
        reasons.append("no new canonical URLs")
    if new_admitted_candidates == 0:
        reasons.append("no new admissible candidates")
    if new_platforms:
        reasons.append(f"{new_platforms} new platform(s)")
    if not reasons:
        reasons.append("round added bounded candidate evidence")
    return MarginalEvidenceGain(
        round_number,
        new_canonical_urls,
        new_admitted_candidates,
        new_platforms,
        new_stories,
        new_aliases,
        network_requests,
        elapsed_ms,
        gain,
        tuple(reasons),
    )


def decide_stop(
    *,
    uncertainty: SearchUncertainty,
    gain: MarginalEvidenceGain,
    result_count: int,
    user_limit: int,
    round_number: int,
    max_rounds: int,
    elapsed_seconds: float,
    max_wall_clock_seconds: float,
    requests_used: int,
    max_requests: int,
    useful_unqueried_sources: int,
    available_sources: int,
    must_attempt_more: bool = False,
) -> StopReason | None:
    if elapsed_seconds >= max_wall_clock_seconds:
        return StopReason.TIME_BUDGET
    if requests_used >= max_requests and useful_unqueried_sources:
        return StopReason.REQUEST_BUDGET
    if result_count >= user_limit and not must_attempt_more:
        return StopReason.USER_LIMIT
    if (
        uncertainty.level == UncertaintyLevel.LOW
        and result_count >= min(10, user_limit)
        and not must_attempt_more
    ):
        return StopReason.SATISFIED
    if round_number > 1 and gain.gain < 0.12:
        return StopReason.LOW_MARGINAL_GAIN
    if useful_unqueried_sources and round_number < max_rounds:
        return None
    if round_number >= max_rounds:
        return StopReason.MAX_ROUNDS
    if available_sources == 0:
        return StopReason.NO_AVAILABLE_SOURCES
    return StopReason.SOURCE_EXHAUSTION


def source_counts(candidates: Iterable[CandidateEvidence]) -> dict[str, int]:
    return dict(Counter(item.source for item in candidates))


def classify_retrieval_outcome(
    *, error_code: str | None, completed: bool, result_count: int
) -> RetrievalOutcome:
    if result_count > 0:
        return RetrievalOutcome.RESULT
    code = (error_code or "").casefold()
    if code in {"captcha_blocked", "http_403", "restricted_access"}:
        return RetrievalOutcome.DISCOVERY_EXTERNALLY_BLOCKED
    if code in {
        "engines_temporarily_unavailable",
        "rate_limited",
        "timeout",
        "dns_network",
        "upstream_5xx",
    }:
        return RetrievalOutcome.ENGINE_UNAVAILABLE
    if completed and not error_code:
        return RetrievalOutcome.NO_RELEVANT_RESULT
    return RetrievalOutcome.CONNECTOR_ERROR
