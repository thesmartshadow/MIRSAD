from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from mirsad_api.connectors import MockConnector
from mirsad_api.database import get_db
from mirsad_api.main import app
from mirsad_api.models import Source
from mirsad_api.services.bootstrap import seed_database


@pytest.mark.asyncio
async def test_saved_bookmark_export_diagnostics_and_data_workflow(db: Session) -> None:
    connectors = {"mock": MockConnector()}
    seed_database(db, connectors)

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            search_request = {
                "query": "public policy",
                "sources": ["mock"],
                "time_range": "7d",
                "language": "all",
                "limit": 3,
                "exact_phrase": False,
                "sort": "best_match",
            }
            created = await client.post("/api/v1/searches", json=search_request)
            assert created.status_code == 201
            search = created.json()
            session_id = search["session"]["id"]
            content_id = search["results"][0]["id"]

            diagnostics = await client.get(f"/api/v1/searches/{session_id}/diagnostics")
            assert diagnostics.status_code == 200
            detail = diagnostics.json()["diagnostics"]
            assert detail["connectors"][0]["normalized_results"] == 5
            assert detail["connectors"][0]["candidate_admitted_results"] == 5
            assert detail["connectors"][0]["final_top_results"] == 3
            assert detail["phase_timings_ms"]["total"] >= 0

            saved = await client.post(
                "/api/v1/saved-searches",
                json={"name": "Policy watch", "configuration": search_request},
            )
            assert saved.status_code == 201
            saved_id = saved.json()["id"]
            rerun = await client.post(f"/api/v1/saved-searches/{saved_id}/run")
            assert rerun.status_code == 200
            renamed = await client.patch(
                f"/api/v1/saved-searches/{saved_id}", json={"name": "Policy review"}
            )
            assert renamed.json()["name"] == "Policy review"
            assert (
                await client.post(f"/api/v1/saved-searches/{saved_id}/duplicate")
            ).status_code == 200

            bookmark = await client.post(
                "/api/v1/bookmarks",
                json={
                    "content_id": content_id,
                    "search_session_id": session_id,
                    "note": "Review for briefing",
                },
            )
            assert bookmark.status_code == 201
            missing_session = await client.post(
                "/api/v1/bookmarks",
                json={
                    "content_id": search["results"][1]["id"],
                    "search_session_id": "missing-session",
                },
            )
            assert missing_session.status_code == 404
            bookmark_id = bookmark.json()["id"]
            updated = await client.patch(
                f"/api/v1/bookmarks/{bookmark_id}", json={"note": "Reviewed"}
            )
            assert updated.json()["note"] == "Reviewed"

            json_export = await client.get(f"/api/v1/searches/{session_id}/export?format=json")
            assert json_export.status_code == 200
            assert json_export.json()["schema"] == "mirsad.search-export"
            assert json_export.json()["records"][0]["query"] == "public policy"
            csv_export = await client.get(f"/api/v1/searches/{session_id}/export?format=csv")
            assert csv_export.status_code == 200
            assert csv_export.content.startswith(b"\xef\xbb\xbfquery,source,source_type")

            counts = (await client.get("/api/v1/data/counts")).json()
            assert counts["bookmarks"] == 1
            rebuilt = await client.post("/api/v1/data/actions/rebuild_fts", json={"confirm": True})
            assert rebuilt.status_code == 200
            assert rebuilt.json()["counts"]["indexed_records"] == counts["content_items"]
            history_cleared = await client.post(
                "/api/v1/data/actions/clear_history", json={"confirm": True}
            )
            assert history_cleared.status_code == 200
            retained_bookmarks = (await client.get("/api/v1/bookmarks")).json()
            assert len(retained_bookmarks) == 1
            assert retained_bookmarks[0]["search_session_id"] is None
            assert retained_bookmarks[0]["content_id"] == content_id
            assert retained_bookmarks[0]["note"] == "Reviewed"
            assert history_cleared.json()["counts"]["content_items"] == counts["content_items"]
            cleared = await client.post(
                "/api/v1/data/actions/clear_bookmarks", json={"confirm": True}
            )
            assert cleared.json()["counts"]["bookmarks"] == 0
            rejected = await client.post(
                "/api/v1/data/actions/reset_database", json={"confirm": False}
            )
            assert rejected.status_code == 422
            assert created.headers["x-content-type-options"] == "nosniff"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sources_exclude_stale_unregistered_connector_rows(db: Session) -> None:
    connectors = {"mock": MockConnector()}
    seed_database(db, connectors)
    db.add(
        Source(
            key="stale_fixture",
            name="Stale Fixture",
            kind="test",
            enabled=True,
            configured=True,
            confidence=50,
            config_public={"configuration_state": "configured"},
        )
    )
    db.commit()
    assert db.scalar(select(Source).where(Source.key == "stale_fixture")) is not None

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/sources")
            assert response.status_code == 200
            assert [source["key"] for source in response.json()] == ["mock"]
    finally:
        app.dependency_overrides.clear()
