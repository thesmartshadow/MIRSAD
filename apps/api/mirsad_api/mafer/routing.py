from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..connectors.base import BaseConnector, CapabilityValue
from .budget import SearchBudget
from .intent import IntentLabel, QueryIntentFingerprint, TemporalIntent

UNAVAILABLE_STATES = {
    "disabled",
    "unconfigured",
    "restricted",
    "unavailable",
    "invalid_credentials",
    "access_limited",
    "external_limit",
    "quota_exhausted",
    "rate_limited",
    "timeout",
    "auth_required",
    "captcha_blocked",
    "temporarily_unavailable",
}


@dataclass(frozen=True, slots=True)
class ResourceObservation:
    historical_yield: float = 0.5
    unique_yield: float = 0.5
    duplicate_rate: float = 0.0
    average_latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class ResourceUtility:
    source: str
    long_term_utility: float
    current_availability: float
    capability_match: float
    query_intent_fit: float
    language_fit: float
    temporal_fit: float
    historical_observed_yield: float
    unique_yield: float
    latency_fit: float
    duplicate_fit: float
    novelty_potential: float
    total: float
    available: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "long_term_utility": round(self.long_term_utility, 2),
            "current_availability": round(self.current_availability, 2),
            "capability_match": round(self.capability_match, 2),
            "query_intent_fit": round(self.query_intent_fit, 2),
            "language_fit": round(self.language_fit, 2),
            "temporal_fit": round(self.temporal_fit, 2),
            "historical_observed_yield": round(self.historical_observed_yield, 2),
            "unique_yield": round(self.unique_yield, 2),
            "latency_fit": round(self.latency_fit, 2),
            "duplicate_fit": round(self.duplicate_fit, 2),
            "novelty_potential": round(self.novelty_potential, 2),
            "total": round(self.total, 2),
            "available": self.available,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ResourcePlan:
    ordered: tuple[ResourceUtility, ...]
    rounds: tuple[tuple[str, ...], ...]
    explicit_selection: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "explicit_selection": self.explicit_selection,
            "rounds": [list(values) for values in self.rounds],
            "resources": [item.as_dict() for item in self.ordered],
        }


def _supported(value: CapabilityValue) -> float:
    if value is True:
        return 1.0
    if value == "conditional":
        return 0.65
    return 0.0


class ResourceRouter:
    """Capability-first retrieval utility; health affects availability, not source purpose."""

    def route(
        self,
        fingerprint: QueryIntentFingerprint,
        connectors: Mapping[str, BaseConnector],
        selected_sources: Iterable[str],
        budget: SearchBudget,
        *,
        explicit_selection: bool,
        current_states: Mapping[str, str] | None = None,
        observations: Mapping[str, ResourceObservation] | None = None,
    ) -> ResourcePlan:
        states = current_states or {}
        history = observations or {}
        selected = tuple(dict.fromkeys(selected_sources))
        utilities: list[ResourceUtility] = []
        for key in selected:
            connector = connectors.get(key)
            if connector is None:
                continue
            utilities.append(
                self.utility(
                    fingerprint,
                    connector,
                    current_state=states.get(key),
                    observation=history.get(key, ResourceObservation()),
                )
            )
        ordered = tuple(sorted(utilities, key=lambda item: (-item.total, item.source)))
        candidates = [item.source for item in ordered if explicit_selection or item.available]
        candidates = candidates[: budget.max_source_calls]
        rounds: list[tuple[str, ...]] = []
        if candidates and explicit_selection:
            # An explicit selection means "query these sources", not "let the
            # adaptive planner defer some of them". Keeping them in one round
            # also preserves Phase-1 concurrent completion-order invariance.
            rounds = [tuple(candidates)]
        elif candidates:
            # Round three is reserved for evidence-gated expansion or historical
            # escalation. Normal source discovery therefore completes within the
            # first two rounds even under DEEP, avoiding a counter-intuitive loss
            # of coverage when uncertainty is already low after round two.
            retrieval_rounds = min(2, budget.max_rounds)
            chunk = max(1, (len(candidates) + retrieval_rounds - 1) // retrieval_rounds)
            rounds = [
                tuple(candidates[index : index + chunk])
                for index in range(0, len(candidates), chunk)
            ]
        return ResourcePlan(ordered, tuple(rounds[: budget.max_rounds]), explicit_selection)

    def utility(
        self,
        fingerprint: QueryIntentFingerprint,
        connector: BaseConnector,
        *,
        current_state: str | None,
        observation: ResourceObservation,
    ) -> ResourceUtility:
        capabilities = connector.metadata.capabilities
        reasons: list[str] = []
        desired: list[tuple[str, CapabilityValue]] = [("keyword", capabilities.keyword_search)]
        if fingerprint.has(IntentLabel.EXACT_PHRASE):
            desired.append(("exact phrase", capabilities.phrase_search))
        if fingerprint.has(IntentLabel.HASHTAG):
            desired.append(("hashtag", capabilities.hashtag_search))
        if fingerprint.has(IntentLabel.HANDLE):
            desired.append(("handle/author", capabilities.author_search))
        if fingerprint.has(IntentLabel.IDENTIFIER):
            desired.append(
                (
                    "identifier",
                    capabilities.identifier_search
                    if hasattr(capabilities, "identifier_search")
                    else capabilities.phrase_search,
                )
            )
        if fingerprint.temporal_intent in {
            TemporalIntent.TIME_CRITICAL,
            TemporalIntent.RECENT_PREFERRED,
        }:
            desired.append(("recent", capabilities.recent_search))
        if fingerprint.temporal_intent == TemporalIntent.HISTORICAL:
            desired.append(("historical", capabilities.historical_search))
        capability_match = 100 * sum(_supported(value) for _name, value in desired) / len(desired)
        supported_names = [name for name, value in desired if _supported(value) > 0]
        if supported_names:
            reasons.append(f"capabilities fit: {', '.join(supported_names)}")

        category = connector.metadata.category
        intent_fit = 55.0
        if fingerprint.has(IntentLabel.HANDLE) or fingerprint.has(IntentLabel.PERSON_LIKE):
            intent_fit = (
                85.0 if capabilities.author_search else 62.0 if category == "social" else 42.0
            )
        elif fingerprint.has(IntentLabel.HASHTAG):
            intent_fit = (
                90.0 if capabilities.hashtag_search else 55.0 if category == "social" else 35.0
            )
        elif fingerprint.has(IntentLabel.IDENTIFIER):
            identifier_capability = getattr(capabilities, "identifier_search", False)
            intent_fit = (
                92.0
                if identifier_capability is True
                else 70.0
                if identifier_capability == "conditional"
                else 45.0
            )
        elif fingerprint.has(IntentLabel.TOPIC):
            intent_fit = 75.0 if capabilities.keyword_search else 35.0
        if fingerprint.has(IntentLabel.AMBIGUOUS):
            intent_fit = min(intent_fit, 68.0)
            reasons.append("ambiguous query limits intent confidence")

        language_fit = 70.0
        if fingerprint.has(IntentLabel.MIXED_LANGUAGE):
            language_fit = 75.0 if capabilities.language_filter else 65.0
        elif fingerprint.has(IntentLabel.ARABIC):
            language_fit = 82.0 if capabilities.language_filter else 68.0
        elif fingerprint.has(IntentLabel.ENGLISH):
            language_fit = 82.0

        if fingerprint.temporal_intent == TemporalIntent.HISTORICAL:
            temporal_fit = 100 * _supported(capabilities.historical_search)
        elif fingerprint.temporal_intent in {
            TemporalIntent.TIME_CRITICAL,
            TemporalIntent.RECENT_PREFERRED,
        }:
            temporal_fit = 100 * _supported(capabilities.recent_search)
        else:
            temporal_fit = 75.0

        configured, configuration_reason = connector.validate_configuration()
        state = (current_state or connector.configuration_state()).casefold()
        available = configured and state not in UNAVAILABLE_STATES
        current_availability = 100.0 if available else 0.0
        if state in {"degraded", "unknown"}:
            current_availability = 55.0
            available = configured
        if not available:
            reasons.append(f"current availability: {state}")
        elif configuration_reason:
            reasons.append(configuration_reason)

        latency_fit = max(20.0, 100.0 - min(observation.average_latency_ms, 8000.0) / 100.0)
        duplicate_fit = max(0.0, 100.0 * (1.0 - min(max(observation.duplicate_rate, 0.0), 1.0)))
        observed_yield = 100.0 * min(max(observation.historical_yield, 0.0), 1.0)
        unique_yield = 100.0 * min(max(observation.unique_yield, 0.0), 1.0)
        novelty = (unique_yield + duplicate_fit) / 2
        long_term = (
            0.27 * capability_match
            + 0.23 * intent_fit
            + 0.10 * language_fit
            + 0.10 * temporal_fit
            + 0.10 * observed_yield
            + 0.08 * unique_yield
            + 0.05 * latency_fit
            + 0.04 * duplicate_fit
            + 0.03 * novelty
        )
        # Availability is intentionally a separate immediate multiplier; it never rewrites
        # long-term source purpose or observed yield.
        total = long_term * (0.25 + 0.75 * current_availability / 100.0)
        return ResourceUtility(
            connector.metadata.key,
            long_term,
            current_availability,
            capability_match,
            intent_fit,
            language_fit,
            temporal_fit,
            observed_yield,
            unique_yield,
            latency_fit,
            duplicate_fit,
            novelty,
            total,
            available,
            tuple(reasons),
        )
