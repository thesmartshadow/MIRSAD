from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from mirsad_api.domains.coverage import build_coverage_report
from mirsad_api.domains.query import process_query
from mirsad_api.mafer.aliases import EntityAliasRepository
from mirsad_api.mafer.intent import QueryIntentAnalyzer
from mirsad_api.mafer.lattice import QueryVariantType, build_query_lattice
from mirsad_api.mafer.learning import LearnedUtility
from mirsad_api.mafer.memory import LocalMemorySearch
from mirsad_api.mafer.routing import ResourcePlan, ResourceUtility
from mirsad_api.mafer.shadow import shadow_route
from mirsad_api.models import ContentItem, EntityAliasEdge, Source
from mirsad_api.provenance import AcquisitionMode


def utility(
    source: str,
    total: float,
    *,
    available: bool = True,
    capability: float = 70.0,
) -> ResourceUtility:
    return ResourceUtility(
        source=source,
        long_term_utility=total,
        current_availability=100.0 if available else 0.0,
        capability_match=capability,
        query_intent_fit=75.0,
        language_fit=75.0,
        temporal_fit=75.0,
        historical_observed_yield=50.0,
        unique_yield=50.0,
        latency_fit=70.0,
        duplicate_fit=90.0,
        novelty_potential=70.0,
        total=total if available else total * 0.25,
        available=available,
        reasons=("fixture capability fit",),
    )


def learned(query_class: str, source: str, adjustment: float) -> LearnedUtility:
    return LearnedUtility(
        query_class,
        source,
        8,
        0,
        adjustment,
        ("deterministic fixture observations",),
    )


def test_adaptive_router_is_shadow_only_and_separates_health_from_utility() -> None:
    resources = tuple(
        utility(key, score, available=key != "gdelt")
        for key, score in (
            ("youtube", 82.0),
            ("bluesky", 79.0),
            ("github", 77.0),
            ("rss", 73.0),
            ("mastodon", 58.0),
            ("gdelt", 80.0),
        )
    )
    production = ResourcePlan(resources, (("youtube", "bluesky", "github"), ("rss",)), False)
    plan = shadow_route(
        production,
        query_class="topic",
        learned={
            ("topic", "mastodon"): learned("topic", "mastodon", -6.0),
            ("topic", "gdelt"): learned("topic", "gdelt", 5.0),
        },
    )
    assert production.rounds == (("youtube", "bluesky", "github"), ("rss",))
    assert "mastodon" in plan.deferred_sources
    assert "gdelt" in plan.deferred_sources
    assert plan.decisions["gdelt"]["long_term_utility"] == 80.0
    assert plan.decisions["gdelt"]["current_availability"] == 0.0
    assert plan.as_dict()["mode"] == "SHADOW_ONLY"


def test_aliases_require_evidence_and_reject_common_name_collision(db: Session) -> None:
    repository = EntityAliasRepository(db)
    assert (
        repository.observe(
            "علي",
            "Ali",
            relationship_type="official_name",
            evidence_source="source-a",
            direct_evidence=True,
        )
        is None
    )
    repository.observe(
        "وزارة التخطيط",
        "Ministry of Planning",
        relationship_type="official_name",
        evidence_source="official-directory",
        evidence_id="entity:planning-ministry",
        direct_evidence=True,
    )
    assert repository.aliases_for("وزارة التخطيط") == ()
    repository.observe(
        "وزارة التخطيط",
        "Ministry of Planning",
        relationship_type="official_name",
        evidence_source="official-feed",
        evidence_id="entity:planning-ministry",
        direct_evidence=True,
    )
    aliases = repository.aliases_for("وزارة التخطيط")
    assert [item.value for item in aliases] == ["Ministry of Planning"]
    assert aliases[0].status == "supported"
    edge = db.scalar(select(EntityAliasEdge))
    assert edge is not None
    assert len(edge.evidence) == 2

    processed = process_query("وزارة التخطيط")
    fingerprint = QueryIntentAnalyzer().analyze(processed, explicit_time_range="all")
    lattice = build_query_lattice(
        processed,
        fingerprint,
        aliases=((aliases[0].value, aliases[0].confidence),),
    )
    expansion = next(
        item for item in lattice.variants if item.transformation == QueryVariantType.ENTITY_ALIAS
    )
    assert expansion.parent_id == lattice.original.variant_id
    assert expansion.drift_risk <= 0.2
    assert "evidenced alias" in expansion.reason


def test_local_memory_is_bounded_and_preserves_historical_timestamp_semantics(
    db: Session,
) -> None:
    source = Source(
        key="rss",
        name="RSS",
        kind="rss",
        enabled=True,
        configured=True,
    )
    db.add(source)
    db.flush()
    published = datetime.now(UTC) - timedelta(days=400)
    first_seen = datetime.now(UTC) - timedelta(days=180)
    retrieved = datetime.now(UTC) - timedelta(days=10)
    item = ContentItem(
        source_id=source.id,
        external_id="planning-2003",
        canonical_url="https://example.test/planning-2003",
        title="Iraq 2003 reconstruction planning",
        text="Historical evidence about Iraq reconstruction planning in 2003.",
        published_at=published,
        fetched_at=retrieved,
        first_seen_at=first_seen,
        last_seen_at=retrieved,
        retrieved_at=retrieved,
        language="en",
        acquisition_mode="PUBLIC_API",
        content_fingerprint="history-fixture",
        raw_metadata={},
        normalized_title="iraq 2003 reconstruction planning",
        normalized_text="historical evidence about iraq reconstruction planning in 2003",
        normalized_author="",
    )
    db.add(item)
    db.commit()
    processed = process_query("Iraq 2003 reconstruction")
    fingerprint = QueryIntentAnalyzer().analyze(processed, explicit_time_range="all")
    lattice = build_query_lattice(processed, fingerprint)
    result = LocalMemorySearch(db).search(
        processed,
        lattice,
        limit=20,
        historical_mode=True,
    )
    assert len(result.items) == 1
    assert result.items[0].acquisition_path == AcquisitionMode.LOCAL_MEMORY
    assert result.items[0].raw_metadata["historical_local_evidence"] is True
    assert result.historical_matches == 1
    assert item.published_at == published
    assert item.first_seen_at == first_seen
    assert item.retrieved_at == retrieved


def test_coverage_separates_successful_results_from_partial_coverage() -> None:
    report = build_coverage_report(
        session_id="session-1",
        outcome_status="completed",
        connector_states={
            "youtube": "healthy",
            "gdelt": "timeout",
            "bluesky": "external_limit",
            "x": "unconfigured",
            "tiktok": "restricted",
        },
        planned_sources=["youtube", "gdelt"],
        connector_rows=[
            {
                "source": "youtube",
                "status": "healthy",
                "attempt_count": 1,
                "fetched_results": 8,
                "final_matching_results": 5,
                "candidate_admitted_results": 5,
                "final_top_results": 3,
                "acquisition_mode": "DIRECT_API",
            },
            {
                "source": "gdelt",
                "status": "degraded",
                "error_category": "timeout",
                "attempt_count": 1,
            },
        ],
        acquisition_funnel=[
            {
                "platform": "youtube",
                "acquisition_path": "DIRECT_API",
                "admitted": 5,
            },
            {
                "platform": "bluesky",
                "acquisition_path": "LOCAL_MEMORY",
                "admitted": 2,
            },
        ],
        final_platforms=["youtube", "youtube", "bluesky"],
        final_acquisition_paths=[
            ("DIRECT_API",),
            ("DIRECT_API",),
            ("LOCAL_MEMORY", "HISTORICAL_INDEX"),
        ],
        historical_local_candidates=1,
        historical_final_flags=[False, False, True],
        historical_final_platforms=["bluesky"],
        resource_plan=[
            {"source": "youtube", "reasons": ["capabilities fit: keyword"]},
            {"source": "gdelt", "reasons": ["capabilities fit: recent"]},
        ],
        stop_reason="USER_LIMIT",
        searxng_enabled=False,
    )
    assert report["outcome_status"] == "completed"
    assert report["coverage_status"] == "PARTIAL"
    reasons = {row["source"]: row["reason"] for row in report["gaps"]}
    assert reasons == {
        "bluesky": "EXTERNAL_LIMIT",
        "gdelt": "TIMEOUT",
        "tiktok": "RESTRICTED",
        "x": "WEB_DISCOVERY_DISABLED",
    }
    local = next(row for row in report["lanes"] if row["lane"] == "LOCAL_MEMORY")
    historical = next(row for row in report["lanes"] if row["lane"] == "HISTORICAL")
    assert local["contributed"] is True
    assert historical["contributed"] is True
    assert historical["final"] == 1
    assert report["stop_explanation"] == (
        "Stopped because the configured result limit was satisfied."
    )
