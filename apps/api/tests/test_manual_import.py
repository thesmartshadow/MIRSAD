from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from mirsad_api.database import get_db
from mirsad_api.main import app
from mirsad_api.models import ContentItem
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.registry import build_connector_registry


@pytest.mark.asyncio
async def test_manual_import_is_non_fetching_validated_and_deduplicated(
    db: Session, settings
) -> None:
    connectors = build_connector_registry(settings)
    seed_database(db, connectors)

    async def override_db() -> AsyncGenerator[Session, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.state.connectors = connectors
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            imported = await client.post(
                "/api/v1/data/manual-import",
                json={
                    "url": "https://twitter.com/public_author/status/123456789?utm_source=test",
                    "title": "Public update",
                    "selected_text": "وزارة التخطيط published a public update.",
                },
            )
            assert imported.status_code == 201
            assert imported.json() == {
                "id": imported.json()["id"],
                "source": "x",
                "canonical_url": "https://x.com/public_author/status/123456789",
                "acquisition_mode": "MANUAL_IMPORT",
                "duplicate": False,
            }
            repeated = await client.post(
                "/api/v1/data/manual-import",
                json={
                    "url": "https://x.com/public_author/status/123456789",
                    "selected_text": "Different operator selection must not duplicate the item.",
                },
            )
            assert repeated.status_code == 201
            assert repeated.json()["duplicate"] is True
            assert repeated.json()["id"] == imported.json()["id"]
            profile = await client.post(
                "/api/v1/data/manual-import",
                json={"url": "https://x.com/public_author", "selected_text": "Profile"},
            )
            unsafe = await client.post(
                "/api/v1/data/manual-import",
                json={"url": "http://127.0.0.1/post/12345", "selected_text": "Local"},
            )
            assert profile.status_code == 422
            assert unsafe.status_code == 422
        item = db.scalar(select(ContentItem))
        assert item is not None
        assert item.acquisition_mode == "MANUAL_IMPORT"
        assert item.raw_metadata["network_fetch_performed"] is False
        assert item.raw_metadata["operator_selected_visible_text"] is True
    finally:
        app.dependency_overrides.clear()
