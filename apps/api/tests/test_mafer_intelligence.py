from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import perf_counter

import httpx
import pytest
from sqlalchemy.orm import Session

from mirsad_api.config import Settings
from mirsad_api.connectors import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorSearchOptions,
)
from mirsad_api.discovery.searxng import DiscoveryProviderError, SearxngClient
from mirsad_api.domains.query import process_query
from mirsad_api.mafer.aliases import EntityAliasRepository
from mirsad_api.mafer.assessment import (
    CandidateEvidence,
    RetrievalOutcome,
    StopReason,
    UncertaintyLevel,
    assess_uncertainty,
    classify_retrieval_outcome,
    decide_stop,
    marginal_evidence_gain,
)
from mirsad_api.mafer.budget import BUDGETS, SearchBudget, SearchMode, budget_for
from mirsad_api.mafer.expansion import propose_evidence_expansions
from mirsad_api.mafer.fusion import (
    DiscoveryRankObservation,
    weighted_reciprocal_rank_fusion,
)
from mirsad_api.mafer.intent import IntentLabel, QueryIntentAnalyzer, TemporalIntent
from mirsad_api.mafer.lattice import QueryVariantType, build_query_lattice
from mirsad_api.mafer.routing import ResourceObservation, ResourceRouter
from mirsad_api.models import SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import get_search_response
from mirsad_api.services.search import SearchService


class PlanningConnector(BaseConnector):
    def __init__(
        self,
        key: str,
        items: list[ConnectorItem] | None = None,
        *,
        capabilities: ConnectorCapabilities | None = None,
        category: str = "social",
        delay: float = 0,
        configured: bool = True,
    ) -> None:
        self.metadata = ConnectorMetadata(
            key=key,
            name=key,
            kind="fixture",
            base_url=f"https://{key}.example",
            category=category,  # type: ignore[arg-type]
            capabilities=capabilities
            or ConnectorCapabilities(
                keyword_search=True,
                phrase_search=True,
                recent_search=True,
                full_text_search=True,
            ),
        )
        super().__init__()
        self.items = items or []
        self.delay = delay
        self.configured = configured
        self.calls: list[ConnectorSearchOptions] = []

    def validate_configuration(self) -> tuple[bool, str | None]:
        return self.configured, None if self.configured else "fixture unavailable"

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.items[:limit]

    async def search_with_options(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None = None,
        options: ConnectorSearchOptions | None = None,
    ) -> list[ConnectorItem]:
        self.calls.append(options or ConnectorSearchOptions())
        return await self.search(query, limit=limit, since=since)

    def normalize(self, payload):
        raise NotImplementedError


def item(source: str, number: int, text: str, *, author: str | None = None) -> ConnectorItem:
    return ConnectorItem(
        source=source,
        external_id=str(number),
        canonical_url=f"https://{source}.example/posts/{number}",
        author=author,
        title=text,
        text=f"{text}. Detailed public evidence for deterministic planning and retrieval.",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        language="und",
        raw_metadata={"source_type": "post", "full_text": True},
    )


def fingerprint(query: str, **kwargs):
    return QueryIntentAnalyzer().analyze(process_query(query), **kwargs)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("@thesmartshadow", {IntentLabel.HANDLE, IntentLabel.IDENTIFIER}),
        ("#بغداد", {IntentLabel.HASHTAG, IntentLabel.ARABIC}),
        ("Microsoft العراق", {IntentLabel.ENTITY_LIKE, IntentLabel.MIXED_LANGUAGE}),
        ('"Ali Firas"', {IntentLabel.EXACT_PHRASE, IntentLabel.PERSON_LIKE}),
        ("apple", {IntentLabel.AMBIGUOUS, IntentLabel.TOPIC}),
        ("https://example.org/report", {IntentLabel.URL, IntentLabel.IDENTIFIER}),
    ],
)
def test_intent_fingerprint_is_multilabel_and_explainable(
    query: str, expected: set[IntentLabel]
) -> None:
    value = fingerprint(query)
    assert expected <= set(value.labels)
    assert all(evidence.reasons for evidence in value.evidence)
    assert 0.99 <= sum(value.script_distribution.values()) <= 1.01


@pytest.mark.parametrize(
    ("query", "present", "absent"),
    [
        ("الذكاء الاصطناعي", {IntentLabel.TOPIC}, {IntentLabel.PERSON_LIKE}),
        ("وزارة التخطيط", {IntentLabel.ENTITY_LIKE}, {IntentLabel.PERSON_LIKE}),
        ("علي فراس محمد رضا", {IntentLabel.PERSON_LIKE}, set()),
        ("علي فراس", {IntentLabel.PERSON_LIKE}, set()),
        ("Linux kernel security", {IntentLabel.TOPIC}, {IntentLabel.PERSON_LIKE}),
        ("@openai", {IntentLabel.HANDLE}, {IntentLabel.PERSON_LIKE}),
        ("#بغداد", {IntentLabel.HASHTAG}, {IntentLabel.PERSON_LIKE}),
        ("CVE-2026-61371", {IntentLabel.IDENTIFIER}, {IntentLabel.PERSON_LIKE}),
    ],
)
def test_intent_person_gating_preserves_names_without_topic_false_positives(
    query: str,
    present: set[IntentLabel],
    absent: set[IntentLabel],
) -> None:
    value = fingerprint(query)
    assert present <= set(value.labels)
    assert not (absent & set(value.labels))


@pytest.mark.parametrize("query", ["CVE-2026-61371", "GHSA-xxxx-xxxx-xxxx", "CWE-59"])
def test_distinctive_identifiers_are_preserved_without_semantic_rewriting(query: str) -> None:
    processed = process_query(query)
    value = fingerprint(query)
    lattice = build_query_lattice(processed, value, max_variants=10)
    assert value.has(IntentLabel.IDENTIFIER)
    assert value.temporal_intent == TemporalIntent.TIME_NEUTRAL
    assert lattice.original.text == query
    assert any(part.transformation == QueryVariantType.IDENTIFIER for part in lattice.variants)
    assert not any(
        part.transformation
        in {QueryVariantType.TRANSLITERATION, QueryVariantType.EVIDENCE_EXPANDED}
        for part in lattice.variants
    )


def test_temporal_intent_respects_explicit_filters_and_historical_terms() -> None:
    assert fingerprint("latest Baghdad news").temporal_intent == TemporalIntent.TIME_CRITICAL
    assert fingerprint("Baghdad 2003").temporal_intent == TemporalIntent.HISTORICAL
    assert (
        fingerprint("artificial intelligence", explicit_time_range="7d").temporal_intent
        == TemporalIntent.RECENT_PREFERRED
    )


def test_arabic_lattice_preserves_diacritized_original_and_bounds_transliteration() -> None:
    diacritized = "وِزَارَةُ التَّخْطِيط"
    processed = process_query(diacritized)
    lattice = build_query_lattice(processed, fingerprint(diacritized), max_variants=5)
    assert lattice.original.text == diacritized
    assert any(
        part.transformation == QueryVariantType.ARABIC_NORMALIZED for part in lattice.variants
    )
    name = process_query("علي فراس")
    name_lattice = build_query_lattice(name, fingerprint(name.original), max_variants=6)
    transliterations = [
        part
        for part in name_lattice.variants
        if part.transformation == QueryVariantType.TRANSLITERATION
    ]
    assert [part.text for part in transliterations] == ["Ali Firas"]
    topic = process_query("الذكاء الاصطناعي")
    topic_lattice = build_query_lattice(topic, fingerprint(topic.original), max_variants=6)
    assert not any(
        part.transformation == QueryVariantType.TRANSLITERATION for part in topic_lattice.variants
    )


def test_query_lattice_is_deterministic_bounded_and_original_is_immutable() -> None:
    processed = process_query("Microsoft العراق")
    value = fingerprint(processed.original)
    first = build_query_lattice(
        processed,
        value,
        max_variants=4,
        aliases=(("Microsoft Iraq", 0.91), ("MS Iraq", 0.85)),
    )
    second = build_query_lattice(
        processed,
        value,
        max_variants=4,
        aliases=(("Microsoft Iraq", 0.91), ("MS Iraq", 0.85)),
    )
    assert len(first.variants) <= 4
    assert first == second
    assert first.variants[0].transformation == QueryVariantType.ORIGINAL
    assert first.variants[0].text == processed.original


def test_resource_routing_separates_long_term_utility_from_current_availability() -> None:
    handle_source = PlanningConnector(
        "handle_source",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            author_search=True,
            recent_search=True,
        ),
    )
    topic_source = PlanningConnector(
        "topic_source",
        capabilities=ConnectorCapabilities(keyword_search=True),
        category="news",
    )
    router = ResourceRouter()
    healthy = router.route(
        fingerprint("@publichandle"),
        {"handle_source": handle_source, "topic_source": topic_source},
        ["topic_source", "handle_source"],
        budget_for(SearchMode.BALANCED),
        explicit_selection=False,
        current_states={"handle_source": "healthy", "topic_source": "healthy"},
    )
    blocked = router.route(
        fingerprint("@publichandle"),
        {"handle_source": handle_source, "topic_source": topic_source},
        ["topic_source", "handle_source"],
        budget_for(SearchMode.BALANCED),
        explicit_selection=False,
        current_states={"handle_source": "captcha_blocked", "topic_source": "healthy"},
    )
    healthy_handle = next(value for value in healthy.ordered if value.source == "handle_source")
    blocked_handle = next(value for value in blocked.ordered if value.source == "handle_source")
    assert healthy_handle.long_term_utility == blocked_handle.long_term_utility
    assert healthy_handle.current_availability == 100
    assert blocked_handle.current_availability == 0
    assert "handle_source" not in {source for values in blocked.rounds for source in values}


def test_resource_observations_affect_utility_without_forced_diversity() -> None:
    connector = PlanningConnector("observed")
    value = ResourceRouter().utility(
        fingerprint("technology"),
        connector,
        current_state="healthy",
        observation=ResourceObservation(
            historical_yield=0.8,
            unique_yield=0.7,
            duplicate_rate=0.2,
            average_latency_ms=250,
        ),
    )
    assert value.available
    assert value.latency_fit > 90
    assert value.duplicate_fit == 80
    assert 0 < value.total <= 100


def test_weighted_rrf_uses_rank_support_not_incompatible_raw_scores() -> None:
    fused = weighted_reciprocal_rank_fusion(
        [
            DiscoveryRankObservation("https://x.test/1", "a", "original", 1),
            DiscoveryRankObservation("https://x.test/2", "a", "original", 2),
            DiscoveryRankObservation("https://x.test/2", "b", "normalized", 1, engine_weight=0.9),
            DiscoveryRankObservation("https://x.test/1", "b", "normalized", 10, engine_weight=0.9),
        ]
    )
    assert fused[0].canonical_url == "https://x.test/2"
    assert fused[0].independent_support == 2
    assert fused[0].engines == ("a", "b")


@pytest.mark.asyncio
async def test_engine_circuit_breaker_cools_down_and_recovers() -> None:
    clock = [0.0]
    blocked = True

    async def handler(_request: httpx.Request) -> httpx.Response:
        if blocked:
            return httpx.Response(
                200,
                json={"results": [], "unresponsive_engines": [["brave", "CAPTCHA"]]},
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org",
                        "title": "recovered",
                        "engine": "brave",
                    }
                ]
            },
        )

    client = SearxngClient(
        "http://127.0.0.1:8080",
        engines=("brave",),
        transport=httpx.MockTransport(handler),
        clock=lambda: clock[0],
    )
    await client.search("first")
    await client.search("second")
    assert client.engine_states()["brave"]["state"] == "CAPTCHA_BLOCKED"
    with pytest.raises(DiscoveryProviderError) as caught:
        await client.search("during cooldown")
    assert caught.value.code == "engines_temporarily_unavailable"
    clock[0] = 301
    blocked = False
    await client.search("recovery probe")
    assert client.engine_states()["brave"]["state"] == "HEALTHY"


def test_uncertainty_marginal_gain_and_stop_reasons_are_explainable() -> None:
    empty = assess_uncertainty([], unqueried_useful_sources=2)
    assert empty.level == UncertaintyLevel.HIGH
    evidence = [
        CandidateEvidence(f"https://example/{index}", f"s{index % 3}", 0.8) for index in range(12)
    ]
    stable = assess_uncertainty(evidence)
    assert stable.level == UncertaintyLevel.LOW
    no_gain = marginal_evidence_gain(
        2,
        new_canonical_urls=0,
        new_admitted_candidates=0,
        new_platforms=0,
        network_requests=4,
        elapsed_ms=500,
    )
    assert no_gain.gain == 0
    assert (
        decide_stop(
            uncertainty=empty,
            gain=no_gain,
            result_count=1,
            user_limit=30,
            round_number=2,
            max_rounds=3,
            elapsed_seconds=1,
            max_wall_clock_seconds=10,
            requests_used=4,
            max_requests=10,
            useful_unqueried_sources=2,
            available_sources=5,
        )
        == StopReason.LOW_MARGINAL_GAIN
    )


def test_external_blocking_is_not_misreported_as_a_successful_zero_result() -> None:
    assert (
        classify_retrieval_outcome(error_code="captcha_blocked", completed=False, result_count=0)
        == RetrievalOutcome.DISCOVERY_EXTERNALLY_BLOCKED
    )
    assert (
        classify_retrieval_outcome(error_code=None, completed=True, result_count=0)
        == RetrievalOutcome.NO_RELEVANT_RESULT
    )
    assert (
        classify_retrieval_outcome(error_code="rate_limited", completed=False, result_count=0)
        == RetrievalOutcome.ENGINE_UNAVAILABLE
    )


def test_gated_expansion_rejects_single_source_topic_drift() -> None:
    value = fingerprint("artificial intelligence policy")
    rejected = propose_evidence_expansions(
        value,
        [
            ("x:1", "artificial intelligence policy celebrity scandal"),
            ("x:2", "artificial intelligence policy celebrity scandal"),
            ("x:3", "artificial intelligence policy celebrity scandal"),
        ],
    )
    assert rejected
    assert not any(candidate.accepted for candidate in rejected)
    cross_source_drift = propose_evidence_expansions(
        value,
        [
            ("x:1", "artificial intelligence policy celebrity scandal"),
            ("rss:2", "artificial intelligence policy celebrity scandal"),
            ("youtube:3", "artificial intelligence policy celebrity scandal"),
        ],
    )
    assert not any(candidate.accepted for candidate in cross_source_drift)
    accepted = propose_evidence_expansions(
        value,
        [
            ("x:1", "artificial intelligence policy BaghdadFramework"),
            ("rss:2", "artificial intelligence policy BaghdadFramework"),
            ("youtube:3", "artificial intelligence policy BaghdadFramework"),
        ],
    )
    assert any(candidate.accepted for candidate in accepted)


def test_alias_graph_requires_independent_support_and_avoids_name_similarity(
    db: Session,
) -> None:
    repository = EntityAliasRepository(db)
    repository.observe(
        "Ali Firas",
        "@alifiras",
        relationship_type="public_handle",
        evidence_source="x",
        direct_evidence=True,
    )
    assert repository.aliases_for("Ali Firas") == ()
    repository.observe(
        "Ali Firas",
        "@alifiras",
        relationship_type="public_handle",
        evidence_source="bluesky",
        direct_evidence=True,
    )
    aliases = repository.aliases_for("Ali Firas")
    assert [value.value for value in aliases] == ["@alifiras"]
    assert repository.aliases_for("Ali Faris") == ()


def test_search_budget_profiles_control_real_work_and_preserve_top_twenty() -> None:
    fast = BUDGETS[SearchMode.FAST]
    balanced = BUDGETS[SearchMode.BALANCED]
    deep = BUDGETS[SearchMode.DEEP]
    assert (
        fast.max_wall_clock_seconds < balanced.max_wall_clock_seconds < deep.max_wall_clock_seconds
    )
    assert fast.max_rounds < balanced.max_rounds < deep.max_rounds
    assert fast.max_source_calls < balanced.max_source_calls < deep.max_source_calls
    assert fast.max_query_variants < balanced.max_query_variants < deep.max_query_variants
    assert {value.max_semantic_candidates for value in BUDGETS.values()} == {20}


@pytest.mark.asyncio
async def test_phase_two_search_is_completion_order_invariant_and_preserves_source_opportunity(
    db: Session, settings: Settings
) -> None:
    alpha = PlanningConnector(
        "alpha",
        [item("alpha", index, f"public technology evidence alpha {index}") for index in range(8)],
        delay=0.03,
    )
    beta = PlanningConnector(
        "beta",
        [item("beta", index, f"public technology evidence beta {index}") for index in range(8)],
        delay=0,
    )
    connectors = {"alpha": alpha, "beta": beta}
    seed_database(db, connectors)
    service = SearchService(db, settings, connectors)
    request = SearchRequest(
        query="public technology evidence",
        sources=["alpha", "beta"],
        source_selection="explicit",
        time_range="all",
        limit=10,
    )
    first_id = await service.execute(request)
    first = get_search_response(db, first_id)
    first_ids = [(value.source, value.external_id) for value in first.results]
    first_completion = db.get(SearchSession, first_id).diagnostics["connector_completion_order"]
    alpha.delay = 0
    beta.delay = 0.03
    second_id = await service.execute(request)
    second = get_search_response(db, second_id)
    second_ids = [(value.source, value.external_id) for value in second.results]
    second_completion = db.get(SearchSession, second_id).diagnostics["connector_completion_order"]
    assert first_completion != second_completion
    assert first_ids == second_ids
    admitted = db.get(SearchSession, second_id).diagnostics["candidate_admission"][
        "admitted_per_source"
    ]
    assert admitted["alpha"] > 0 and admitted["beta"] > 0


@pytest.mark.asyncio
async def test_round_zero_can_satisfy_time_neutral_auto_search_without_network_replay(
    db: Session, settings: Settings
) -> None:
    connectors = {
        source: PlanningConnector(
            source,
            [
                item(source, index, f"federated memory evidence {source} {index}")
                for index in range(5)
            ],
        )
        for source in ("one", "two", "three")
    }
    seed_database(db, connectors)
    service = SearchService(db, settings, connectors)
    await service.execute(
        SearchRequest(
            query="federated memory evidence",
            sources=list(connectors),
            source_selection="explicit",
            time_range="all",
            limit=10,
        )
    )
    call_count = sum(len(connector.calls) for connector in connectors.values())
    session_id = await service.execute(
        SearchRequest(
            query="federated memory evidence",
            sources=list(connectors),
            source_selection="auto",
            time_range="all",
            limit=10,
        )
    )
    session = db.get(SearchSession, session_id)
    assert sum(len(connector.calls) for connector in connectors.values()) == call_count
    assert session.diagnostics["mafer"]["stop_reason"] == "SATISFIED"
    assert session.diagnostics["mafer"]["rounds"][0]["kind"] == "LOCAL_MEMORY"


@pytest.mark.asyncio
async def test_wall_clock_budget_keeps_completed_sources_and_cancels_only_slow_work(
    db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        BUDGETS,
        SearchMode.FAST,
        SearchBudget(SearchMode.FAST, 0.08, 1, 3, 2, 3, 20, 30, 20, 0),
    )
    connectors = {
        "fast": PlanningConnector(
            "fast", [item("fast", 1, "bounded planning evidence")], delay=0.01
        ),
        "slow": PlanningConnector(
            "slow", [item("slow", 1, "bounded planning evidence")], delay=0.3
        ),
    }
    seed_database(db, connectors)
    started = perf_counter()
    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(
            query="bounded planning evidence",
            sources=["fast", "slow"],
            source_selection="explicit",
            search_mode="fast",
            time_range="all",
            limit=10,
        )
    )
    elapsed = perf_counter() - started
    response = get_search_response(db, session_id)
    assert elapsed < 0.2
    assert [result.source for result in response.results] == ["fast"]
    assert response.session.status == "partial"
    assert {warning.source: warning.code for warning in response.session.warnings}[
        "slow"
    ] == "timeout"
    assert response.session.parameters.search_mode == SearchMode.FAST


@pytest.mark.asyncio
async def test_web_discovery_budgets_are_global_across_adaptive_rounds(
    db: Session, settings: Settings
) -> None:
    web = PlanningConnector(
        "web",
        [item("web", 1, "Ali Firas public profile evidence", author="Ali Firas")],
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            author_search=True,
            web_index_search=True,
            historical_search=True,
            acquisition_modes=("WEB_INDEX",),
        ),
    )
    connectors = {"web": web}
    seed_database(db, connectors)
    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(
            query="Ali Firas",
            sources=["web"],
            source_selection="explicit",
            search_mode="deep",
            time_range="all",
            source_options={"web": {"historical": True}},
            limit=10,
        )
    )

    budget = budget_for(SearchMode.DEEP)
    assert len(web.calls) == 2
    assert sum(call.max_discovery_engine_calls for call in web.calls) <= (
        budget.max_discovery_engine_calls
    )
    assert sum(call.max_discovered_urls for call in web.calls) <= budget.max_discovered_urls
    assert sum(call.max_historical_calls for call in web.calls) <= budget.max_historical_calls
    assert all(call.max_discovery_engine_calls > 0 for call in web.calls)
    diagnostics = db.get(SearchSession, session_id).diagnostics["mafer"]
    assert diagnostics["stop_reason"] == "SATISFIED"
    assert diagnostics["discovery_budget"]["engine_calls_remaining"]["web"] == 0
