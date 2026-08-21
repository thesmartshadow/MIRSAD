from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime

import httpx
import pytest
from sqlalchemy.orm import Session

from mirsad_api.connectors import ConnectorError, ConnectorMetadata, MockConnector
from mirsad_api.database import get_db
from mirsad_api.main import app
from mirsad_api.services.bootstrap import seed_database


class ApiFailingConnector(MockConnector):
    metadata = ConnectorMetadata(
        key="api_failure",
        name="API failure fixture",
        kind="test",
        base_url="mock://api-failure",
    )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        raise ConnectorError("api_failure", "fixture_failure", "Fixture source unavailable")


@pytest.mark.asyncio
async def test_api_search_partial_failure_history_and_settings(db: Session) -> None:
    connectors = {"mock": MockConnector(), "api_failure": ApiFailingConnector()}
    seed_database(db, connectors)

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            empty = await client.post(
                "/api/v1/searches", json={"query": "   ", "sources": ["mock"]}
            )
            assert empty.status_code == 422
            punctuation = await client.post(
                "/api/v1/searches", json={"query": "!!!", "sources": ["mock"]}
            )
            assert punctuation.status_code == 422

            response = await client.post(
                "/api/v1/searches",
                json={
                    "query": "public policy",
                    "sources": ["mock", "api_failure"],
                    "limit": 2,
                    "time_range": "7d",
                    "language": "all",
                    "sort": "best_match",
                },
            )
            assert response.status_code == 201
            body = response.json()
            assert body["session"]["status"] == "partial"
            assert len(body["results"]) == 2
            assert body["session"]["warnings"][0]["source"] == "api_failure"
            assert body["results"][0]["explanation"]["source"] == "mock"
            assert body["session"]["started_at"].endswith("Z")
            assert body["results"][0]["fetched_at"].endswith("Z")

            history = await client.get("/api/v1/searches")
            assert history.status_code == 200
            assert history.json()[0]["id"] == body["session"]["id"]

            reopened = await client.get(f"/api/v1/searches/{body['session']['id']}")
            assert reopened.status_code == 200
            assert reopened.json()["session"]["original_query"] == "public policy"

            invalid_weights = await client.put(
                "/api/v1/settings", json={"values": {"ranking.relevance": 0.9}}
            )
            assert invalid_weights.status_code == 422
            invalid_limit = await client.put(
                "/api/v1/settings",
                json={"values": {"general.default_result_limit": -1}},
            )
            assert invalid_limit.status_code == 422
            invalid_theme = await client.put(
                "/api/v1/settings", json={"values": {"appearance.theme": "neon"}}
            )
            assert invalid_theme.status_code == 422
            boolean_weights = await client.put(
                "/api/v1/settings",
                json={
                    "values": {
                        "ranking.relevance": True,
                        "ranking.freshness": False,
                        "ranking.engagement": False,
                        "ranking.source_confidence": False,
                        "ranking.cross_source_presence": False,
                        "ranking.novelty": False,
                    }
                },
            )
            assert boolean_weights.status_code == 422

            valid_weights = await client.put(
                "/api/v1/settings",
                json={
                    "values": {
                        "ranking.relevance": 0.4,
                        "ranking.freshness": 0.15,
                    }
                },
            )
            assert valid_weights.status_code == 200
            settings = {item["key"]: item["value"] for item in valid_weights.json()}
            assert settings["ranking.relevance"] == 0.4
            assert settings["ranking.freshness"] == 0.15
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_openapi_and_request_size_limit() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/health")).status_code == 200
        openapi = await client.get("/api/v1/openapi.json")
        assert openapi.status_code == 200
        assert "/api/v1/searches" in openapi.json()["paths"]
        oversized = await client.post(
            "/api/v1/searches",
            content=b"x" * 70_000,
            headers={"Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
