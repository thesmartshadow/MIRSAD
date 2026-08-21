from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
)


class MockConnector(BaseConnector):
    """Explicit deterministic development/test connector; never enabled implicitly."""

    metadata = ConnectorMetadata(
        key="mock",
        name="Deterministic Mock",
        kind="test",
        base_url="mock://local",
        confidence=60,
        category="developer_community",
        coverage_label="Explicit deterministic development fixture",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            recent_search=True,
            language_filter=True,
            date_filter=True,
            public_posts=True,
            engagement_metrics=True,
            pagination=True,
            content_types=("posts",),
        ),
    )

    def __init__(self, *, fail: bool = False, latency: float = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fail = fail
        self.latency = latency

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, "Explicit test/development source"

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        await asyncio.sleep(self.latency)
        if self.fail:
            raise ConnectorError("mock", "mock_failure", "Deterministic connector failure")
        now = datetime.now(UTC)
        query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
        fixtures = [
            {
                "id": f"mock-{query_key}-{index}",
                "title": f"{query} public briefing {index + 1}",
                "text": (
                    f"Deterministic fixture about {query} for local workflow validation, "
                    f"item {index + 1}."
                ),
                "published_at": now - timedelta(hours=index * 3),
                "likes": 5 + index * 7,
            }
            for index in range(5)
        ]
        return self.normalize_payloads(fixtures[:limit])

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        external_id = str(payload["id"])
        return ConnectorItem(
            source="mock",
            external_id=external_id,
            canonical_url=f"https://example.invalid/mirsad-fixture/{external_id}",
            author="MIRSAD fixture",
            title=payload.get("title"),
            text=str(payload.get("text", "")),
            published_at=payload.get("published_at"),
            language="en",
            raw_metrics={"likes": payload.get("likes", 0), "shares": 1, "comments": 2},
            raw_metadata={"source_type": "fixture", "fixture": True},
        )
