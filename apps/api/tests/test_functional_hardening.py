from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from mirsad_api.connectors import ConnectorError, MockConnector
from mirsad_api.connectors.base import exact_query_text
from mirsad_api.database import get_db
from mirsad_api.main import app
from mirsad_api.models import AnalyticsRecord, SearchQuery, SearchSession, SourceHealth
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.search import ConnectorRun, SearchService


@pytest.mark.asyncio
async def test_global_analytics_uses_persisted_content_after_latest_zero_session(
    db: Session,
) -> None:
    connectors = {"mock": MockConnector()}
    seed_database(db, connectors)

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/searches",
                json={"query": "public policy", "sources": ["mock"], "limit": 3},
            )
            assert created.status_code == 201
            nonzero_id = created.json()["session"]["id"]

            query = SearchQuery(
                original_query="CVE-2026-61371",
                normalized_query="cve-2026-61371",
                detected_language="en",
                tokens=["cve-2026-61371"],
                variants=["CVE-2026-61371"],
                exact_phrase=False,
            )
            db.add(query)
            db.flush()
            zero = SearchSession(
                query_id=query.id,
                status="completed",
                sources=["mock"],
                parameters={"query": query.original_query, "sources": ["mock"]},
                warnings=[],
                diagnostics={"outcome": {"reason": "NO_MATCHES"}},
                result_count=0,
                unique_count=0,
                duration_ms=1,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            db.add(zero)
            db.flush()
            db.add(
                AnalyticsRecord(
                    search_session_id=zero.id,
                    metric_key="snapshot",
                    value=created.json()["analytics"] | {
                        "total_results": 0,
                        "unique_results": 0,
                    },
                )
            )
            db.commit()

            global_response = await client.get("/api/v1/analytics?scope=all")
            assert global_response.status_code == 200
            global_body = global_response.json()
            assert global_body["scope"] == "all"
            assert global_body["content_record_count"] == 5
            assert global_body["unique_canonical_count"] == 5
            assert global_body["search_appearance_count"] == 3
            assert global_body["source_count"] == 1

            session_response = await client.get(f"/api/v1/analytics/{zero.id}")
            assert session_response.status_code == 200
            assert session_response.json()["scope"] == "session"
            assert session_response.json()["scope_query"] == "CVE-2026-61371"
            assert session_response.json()["total_results"] == 0

            reopened = await client.get(f"/api/v1/searches/{nonzero_id}")
            assert reopened.json()["session"]["result_count"] == 3
            assert reopened.json()["analytics"]["total_results"] == 3
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_partial_connector_results_degrade_then_recover_health(
    db: Session, settings
) -> None:
    connector = MockConnector()
    service = SearchService(db, settings, {"mock": connector})
    item = (await connector.search("recovery", limit=1))[0]
    service._update_health(
        [
            ConnectorRun(
                "mock",
                [item],
                15,
                ConnectorError("mock", "http_403", "later page forbidden", status_code=403),
                normalized_result_count=1,
            )
        ]
    )
    db.flush()
    health = db.scalar(select(SourceHealth))
    assert health is not None
    assert health.status == "degraded"
    assert health.last_success_at is not None
    assert health.failure_category == "http_403"

    service._update_health([ConnectorRun("mock", [], 4)])
    assert health.status == "healthy"
    assert health.failure_category is None
    assert health.recent_failure is None


def test_exact_query_is_quoted_once_and_identifiers_are_preserved() -> None:
    assert exact_query_text('"وزارة التخطيط"', True) == '"وزارة التخطيط"'
    assert exact_query_text("CVE-2026-61371", True) == '"CVE-2026-61371"'
    assert exact_query_text("CVE-2026-61371", False) == "CVE-2026-61371"


def test_zero_result_outcome_distinguishes_time_and_external_failure() -> None:
    from mirsad_api.schemas import SearchRequest

    time_result = SearchService._search_outcome(
        request=SearchRequest(query="CVE-2026-61371", sources=["mock"], time_range="7d"),
        planned_sources=["mock"],
        runs=[
            ConnectorRun(
                "mock",
                [],
                1,
                query_match_count=1,
                time_eligible_count=0,
            )
        ],
        result_count=0,
    )
    assert time_result["reason"] == "NO_MATCHES_IN_TIME_RANGE"

    external_result = SearchService._search_outcome(
        request=SearchRequest(query="test", sources=["mock"]),
        planned_sources=["mock"],
        runs=[
            ConnectorRun(
                "mock",
                [],
                1,
                ConnectorError("mock", "timeout", "timed out"),
            )
        ],
        result_count=0,
    )
    assert external_result["reason"] == "ALL_SELECTED_SOURCES_FAILED"
    assert external_result["cause"] == "EXTERNAL_LIMIT"


@pytest.mark.asyncio
async def test_nonprobing_health_refresh_preserves_observed_state(db: Session) -> None:
    connectors = {"mock": MockConnector()}
    seed_database(db, connectors)
    health = db.scalar(select(SourceHealth))
    assert health is not None
    health.status = "healthy"
    health.last_success_at = datetime.now(UTC)
    db.commit()

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/sources/health")
            assert response.status_code == 200
            assert response.json()[0]["status"] == "healthy"
    finally:
        app.dependency_overrides.clear()
