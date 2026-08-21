from __future__ import annotations

from datetime import datetime
from typing import Any

from ..provenance import AcquisitionMode
from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorValidation,
    parse_datetime,
)
from .social_utils import available_metrics


class HackerNewsConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="hacker_news",
        name="Hacker News",
        kind="community",
        base_url="https://hn.algolia.com",
        confidence=70,
        category="developer_community",
        coverage_label="Public Hacker News records indexed by Algolia",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            author_search=True,
            recent_search=True,
            historical_search=True,
            date_filter=True,
            comments=True,
            engagement_metrics=True,
            pagination=True,
            full_text_search=True,
            identifier_search="conditional",
            content_types=("posts",),
            acquisition_modes=("PUBLIC_API",),
        ),
    )

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def validate_access(self) -> ConnectorValidation:
        await self.request_json(
            "GET",
            f"{self.metadata.base_url}/api/v1/search",
            params={"query": "open source", "hitsPerPage": 1},
        )
        return ConnectorValidation(
            "pass", "public_endpoint_available", "Public search endpoint is available", True
        )

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        params: dict[str, Any] = {"query": query, "hitsPerPage": min(limit, 100)}
        if since:
            params["numericFilters"] = f"created_at_i>{int(since.timestamp())}"
        payload, _latency = await self.request_json(
            "GET", f"{self.metadata.base_url}/api/v1/search_by_date", params=params
        )
        hits = payload.get("hits", [])
        if not isinstance(hits, list):
            raise TypeError("Hacker News hits payload must be a list")
        return self.normalize_payloads(hits)

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        object_id = str(payload.get("objectID", "unknown"))
        title = payload.get("title") or payload.get("story_title")
        text = payload.get("story_text") or payload.get("comment_text") or title or ""
        return ConnectorItem(
            source=self.metadata.key,
            external_id=object_id,
            canonical_url=payload.get("url")
            or payload.get("story_url")
            or f"https://news.ycombinator.com/item?id={object_id}",
            author=payload.get("author"),
            title=title,
            text=str(text),
            published_at=parse_datetime(payload.get("created_at") or payload.get("created_at_i")),
            language="en",
            raw_metrics=available_metrics(
                payload, {"points": "points", "comments": "num_comments"}
            ),
            raw_metadata={"story_id": payload.get("story_id"), "tags": payload.get("_tags", [])},
            acquisition_mode=AcquisitionMode.PUBLIC_API,
        )
