from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import datetime

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from mirsad_api.connectors import ConnectorError, ConnectorMetadata, MockConnector
from mirsad_api.database import get_db
from mirsad_api.main import app
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import relevant_snippet
from mirsad_api.services.search_jobs import SearchJobCapacityError, SearchJobRegistry


class FailingConnector(MockConnector):
    metadata = ConnectorMetadata(
        key="failure",
        name="Failure",
        kind="test",
        base_url="mock://failure",
    )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        raise ConnectorError("failure", "timeout", "Fixture timed out", retryable=True)


class SlowConnector(MockConnector):
    metadata = ConnectorMetadata(
        key="slow",
        name="Slow",
        kind="test",
        base_url="mock://slow",
    )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        await asyncio.sleep(0.05)
        return [
            replace(item, source="slow")
            for item in await super().search(query, limit=limit, since=since)
        ]


def event_payloads(body: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_relevant_snippet_is_plain_text_with_bounded_ranges() -> None:
    snippet, ranges = relevant_snippet(
        '<script>alert("x")</script> Public policy evidence', ["public policy"]
    )
    assert "<script>" in snippet
    assert len(ranges) == 1
    assert snippet[ranges[0].start : ranges[0].end] == "Public policy"


@pytest.mark.asyncio
async def test_search_job_sse_orders_progress_and_finalizes_partial(
    db: Session, test_engine, settings
) -> None:
    connectors = {"mock": MockConnector(), "failure": FailingConnector()}
    seed_database(db, connectors)
    factory = sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    registry = SearchJobRegistry(factory, ttl_seconds=60, max_entries=8, event_limit=64)

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    app.state.search_jobs = registry
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/search/jobs",
                json={
                    "query": "public policy",
                    "sources": ["mock", "failure"],
                    "source_selection": "explicit",
                    "time_range": "all",
                    "limit": 4,
                },
            )
            assert created.status_code == 202
            job = created.json()
            assert job["status"] == "started"
            response = await client.get(f"/api/v1/search/jobs/{job['job_id']}/events")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            events = event_payloads(response.text)
            names = [event["event"] for event in events]
            assert names[0] == "search.started"
            assert names.index("planning.started") < names.index("planning.completed")
            assert "source.completed" in names
            assert "source.failed" in names
            assert names[-1] == "search.partial"
            assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
            final = events[-1]["data"]
            assert final["status"] == "partial"
            assert final["result_count"] > 0
    finally:
        await registry.shutdown()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_job_registry_is_bounded_expires_and_disconnect_is_safe(
    test_engine, settings
) -> None:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    connector = SlowConnector()
    with factory() as db:
        seed_database(db, {"slow": connector})
    registry = SearchJobRegistry(factory, ttl_seconds=60, max_entries=1, event_limit=4)
    request = SearchRequest(
        query="public policy",
        sources=["slow"],
        source_selection="explicit",
        time_range="all",
    )
    first = registry.start(request, settings, {"slow": connector})
    with pytest.raises(SearchJobCapacityError):
        registry.start(request, settings, {"slow": connector})
    job = registry.get(first.job_id)
    assert job is not None
    stream = registry.events(job)
    await anext(stream)
    await stream.aclose()
    assert job.task is not None and not job.task.cancelled()
    await job.task
    assert job.terminal
    assert len(job.events) <= 4
    assert job.events[-1].event == "search.completed"
    job.created_monotonic -= 61
    registry.cleanup()
    assert registry.get(first.job_id) is None
