from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mirsad_api.connectors import MockConnector
from mirsad_api.database import get_db
from mirsad_api.mafer.calibration import (
    ObservableSearchEvidence,
    SaturationDecision,
    calibrated_uncertainty,
    saturation_decision,
)
from mirsad_api.mafer.configuration import (
    PREVIOUS_PRODUCTION,
    VERIFIED_PRODUCTION,
    active_snapshot,
    create_snapshot,
    ensure_configuration_snapshots,
    rollback_one_step,
)
from mirsad_api.mafer.evidence_graph import EvidenceGraphRepository
from mirsad_api.mafer.learning import ShadowUtilityLearner
from mirsad_api.mafer.shadow_ranking import (
    ShadowRankedItem,
    fusion_order,
    near_tie_diversity_order,
)
from mirsad_api.mafer.versions import production_versions
from mirsad_api.main import app
from mirsad_api.models import (
    ContentItem,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    SourceUtilityObservation,
)
from mirsad_api.services.bootstrap import seed_database

ROOT = Path(__file__).resolve().parents[3]
HOLDOUT = ROOT / "apps/api/tests/fixtures/mafer_phase3_holdout.json"
HOLDOUT_SHA256 = "50b06e990e39e41995893b4de288553d16d4f575ca2d825554039004b23b5ca2"


def evidence(**overrides: object) -> ObservableSearchEvidence:
    values: dict[str, object] = {
        "candidate_count": 20,
        "source_count": 4,
        "healthy_unqueried_sources": 0,
        "variant_agreement": 0.8,
        "lexical_semantic_disagreement": 10.0,
        "rank_margin": 12.0,
        "evidence_completeness": 0.8,
        "single_engine_dependence": False,
        "round_number": 2,
        "previous_unique_gain": 12,
        "current_unique_gain": 5,
        "previous_admitted_gain": 10,
        "current_admitted_gain": 4,
    }
    values.update(overrides)
    return ObservableSearchEvidence(**values)  # type: ignore[arg-type]


def test_phase_three_holdout_is_frozen_and_independent() -> None:
    assert hashlib.sha256(HOLDOUT.read_bytes()).hexdigest() == HOLDOUT_SHA256
    payload = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 18
    assert len({case["query"] for case in payload["cases"]}) == 18
    assert sum(case["language"] in {"arabic", "mixed"} for case in payload["cases"]) >= 8


def test_calibrated_uncertainty_orders_observable_retrieval_risk() -> None:
    low = calibrated_uncertainty(evidence())
    medium = calibrated_uncertainty(
        evidence(source_count=2, healthy_unqueried_sources=1, evidence_completeness=0.6)
    )
    high = calibrated_uncertainty(
        evidence(
            candidate_count=4,
            source_count=1,
            healthy_unqueried_sources=4,
            variant_agreement=0.2,
            lexical_semantic_disagreement=40,
            rank_margin=1,
            evidence_completeness=0.3,
            single_engine_dependence=True,
            round_number=1,
        )
    )
    assert low.risk_points < medium.risk_points < high.risk_points
    assert [low.level.value, medium.level.value, high.level.value] == ["LOW", "MEDIUM", "HIGH"]


def test_shadow_saturation_uses_remaining_coverage_and_marginal_gain() -> None:
    uncertain = calibrated_uncertainty(evidence(healthy_unqueried_sources=2, source_count=2))
    continuing = saturation_decision(
        evidence(healthy_unqueried_sources=2, source_count=2, round_number=1),
        uncertain,
        elapsed_seconds=1,
        max_wall_clock_seconds=25,
        requests_used=4,
        max_requests=20,
        round_number=1,
        max_rounds=3,
    )
    saturated_evidence = evidence(
        healthy_unqueried_sources=1,
        previous_unique_gain=20,
        current_unique_gain=1,
        previous_admitted_gain=15,
        current_admitted_gain=1,
    )
    saturated = saturation_decision(
        saturated_evidence,
        calibrated_uncertainty(saturated_evidence),
        elapsed_seconds=2,
        max_wall_clock_seconds=25,
        requests_used=8,
        max_requests=20,
        round_number=2,
        max_rounds=3,
    )
    assert continuing.decision == SaturationDecision.CONTINUE
    assert "retrieval uncertainty" in continuing.evidence[0]
    assert "confidence" not in continuing.evidence[0]
    assert saturated.decision == SaturationDecision.STOP
    assert saturated.reason == "LOW_MARGINAL_GAIN"


def test_shadow_learning_requires_evidence_and_is_bounded(db: Session) -> None:
    now = datetime.now(UTC)
    for index in range(4):
        db.add(
            SourceUtilityObservation(
                query_class="entity_like",
                source="bluesky",
                selected=True,
                available=True,
                returned_count=10,
                unique_count=9,
                admitted_count=8,
                top_k_count=6,
                latency_ms=100,
                created_at=now - timedelta(days=index),
            )
        )
    db.commit()
    utility = ShadowUtilityLearner(db, now=now).source_utilities()[("entity_like", "bluesky")]
    assert utility.adjustment == 0
    db.add(
        SourceUtilityObservation(
            query_class="entity_like",
            source="bluesky",
            selected=True,
            available=True,
            returned_count=10,
            unique_count=10,
            admitted_count=10,
            top_k_count=10,
            latency_ms=1,
            duplicate_rate=0,
            created_at=now,
        )
    )
    db.commit()
    utility = ShadowUtilityLearner(db, now=now).source_utilities()[("entity_like", "bluesky")]
    assert 0 < utility.adjustment <= 8


def test_empty_and_malformed_learning_history_falls_back_safely(db: Session) -> None:
    assert ShadowUtilityLearner(db).source_utilities() == {}
    db.add(
        SourceUtilityObservation(
            query_class="topic",
            source="rss",
            selected=True,
            available=False,
            returned_count=-5,
            unique_count=-2,
            admitted_count=-1,
            top_k_count=0,
            latency_ms=1_000_000,
            duplicate_rate=9,
        )
    )
    db.commit()
    value = ShadowUtilityLearner(db).source_utilities()[("topic", "rss")]
    assert value.adjustment == 0
    assert "minimum evidence" in value.reasons[0]


def test_shadow_fusion_and_diversity_are_deterministic_and_bounded() -> None:
    candidates = [
        (1, "rss", 98.0, 70.0),
        (2, "youtube", 75.0, 96.0),
        (3, "bluesky", 72.0, 93.0),
    ]
    identity_order = fusion_order(candidates, lexical_weight=0.7)
    topic_order = fusion_order(candidates, lexical_weight=0.25)
    assert identity_order == fusion_order(list(reversed(candidates)), lexical_weight=0.7)
    assert identity_order != topic_order
    diverse = near_tie_diversity_order(
        [
            ShadowRankedItem(1, "rss", 90.0, "story-a"),
            ShadowRankedItem(2, "rss", 89.5, "story-a"),
            ShadowRankedItem(3, "bluesky", 89.0, "story-b"),
            ShadowRankedItem(4, "youtube", 60.0, "story-c"),
        ]
    )
    assert diverse[:2] == [1, 3]
    assert diverse[-1] == 4


def test_configuration_snapshot_rollback_does_not_touch_content(db: Session) -> None:
    ensure_configuration_snapshots(db, benchmark_hashes={"phase2": "abc"})
    current = active_snapshot(db, VERIFIED_PRODUCTION)
    assert current is not None
    create_snapshot(
        db,
        slot=PREVIOUS_PRODUCTION,
        configuration={**production_versions(), "router_version": "previous-router"},
        benchmark_hashes={"phase2": "previous"},
        metrics={"p_at_5": 0.8},
        reason="Rollback fixture",
    )
    content_count = db.scalar(select(func.count(ContentItem.id))) or 0
    restored = rollback_one_step(db, reason="regression test")
    db.commit()
    assert restored.configuration["router_version"] == "previous-router"
    assert (db.scalar(select(func.count(ContentItem.id))) or 0) == content_count


def test_evidence_graph_records_observations_without_identity_claims(db: Session) -> None:
    graph = EvidenceGraphRepository(db)
    graph.observe_result(
        query="وزارة التخطيط",
        content_public_id="content-1",
        canonical_url="https://example.com/report",
        source="rss",
        author_handle="planning",
        hashtags=["العراق"],
        cluster_id="story-1",
        session_id="session-1",
    )
    db.commit()
    relationships = set(db.scalars(select(EvidenceGraphEdge.relationship_type)).all())
    assert {"discovered_by", "links_to", "published_on", "mentions", "same_story"} <= relationships
    assert not relationships.intersection({"same_person", "caused_by", "is_true"})
    assert (db.scalar(select(func.count(EvidenceGraphNode.id))) or 0) >= 7


@pytest.mark.asyncio
async def test_quality_api_validates_result_ownership_and_records_explicit_feedback(
    db: Session,
) -> None:
    connectors = {"mock": MockConnector()}
    seed_database(db, connectors)

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/searches",
                json={"query": "public policy", "sources": ["mock"], "limit": 2},
            )
            assert created.status_code == 201
            payload = created.json()
            session_id = payload["session"]["id"]
            content_id = payload["results"][0]["id"]
            event = await client.post(
                "/api/v1/quality/events",
                json={
                    "event_type": "RESULT_MARKED_RELEVANT",
                    "search_session_id": session_id,
                    "content_id": content_id,
                },
            )
            assert event.status_code == 201
            assert event.json()["explicit_judgment"] == "relevant"
            summary = await client.get("/api/v1/quality")
            assert summary.status_code == 200
            assert summary.json()["explicit_relevant"] == 1
            assert summary.json()["shadow_comparisons"]["router"] == 1
            reformulated = await client.post(
                "/api/v1/quality/events",
                json={
                    "event_type": "SEARCH_REFORMULATED",
                    "search_session_id": session_id,
                },
            )
            assert reformulated.status_code == 201
            assert reformulated.json()["content_id"] is None
            assert reformulated.json()["explicit_judgment"] is None
            wrong_session = "00000000-0000-0000-0000-000000000000"
            rejected = await client.post(
                "/api/v1/quality/events",
                json={
                    "event_type": "RESULT_OPENED",
                    "search_session_id": wrong_session,
                    "content_id": content_id,
                },
            )
            assert rejected.status_code == 404
    finally:
        app.dependency_overrides.clear()
