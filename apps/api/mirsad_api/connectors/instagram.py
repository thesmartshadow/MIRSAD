from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorSearchOptions,
    ConnectorValidation,
    parse_datetime,
)
from .social_utils import available_metrics, extract_entities


class InstagramConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="instagram",
        name="Instagram",
        kind="social",
        base_url="https://graph.facebook.com",
        requires_credentials=True,
        confidence=60,
        category="social",
        support_level="supported_with_credentials",
        coverage_label="Hashtagged public media only; no global keyword search",
        capabilities=ConnectorCapabilities(
            keyword_search=False,
            phrase_search=False,
            hashtag_search=True,
            recent_search=True,
            historical_search="conditional",
            date_filter=False,
            public_posts="conditional",
            engagement_metrics=True,
            pagination=True,
            requires_credentials=True,
            requires_approval=True,
            content_types=("posts", "videos"),
            search_modes=("hashtag",),
            sort_modes=("recent",),
        ),
    )

    def __init__(
        self,
        access_token: str | None = None,
        user_id: str | None = None,
        graph_version: str = "v23.0",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.access_token = access_token
        self.user_id = user_id
        self.graph_version = graph_version.strip("/")

    def validate_configuration(self) -> tuple[bool, str | None]:
        configured = bool(self.access_token and self.user_id)
        return (
            configured,
            None if configured else "Professional account hashtag access not configured",
        )

    async def validate_access(self) -> ConnectorValidation:
        if not self.validate_configuration()[0]:
            return await super().validate_access()
        await self.request_json(
            "GET",
            f"{self.metadata.base_url}/{self.graph_version}/{self.user_id}",
            params={"fields": "id"},
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        return ConnectorValidation(
            "pass", "credentials_valid", "Professional account token accepted", True
        )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        return await self.search_with_options(query, limit=limit, since=since)

    async def search_with_options(
        self, query: str, *, limit: int, since=None, options: ConnectorSearchOptions | None = None
    ):
        if not self.validate_configuration()[0]:
            raise ConnectorError(
                "instagram",
                "configuration_missing",
                "Professional account hashtag access not configured",
            )
        mode = (options.for_source("instagram") if options else {}).get("mode")
        if mode != "hashtag" and not query.lstrip().startswith("#"):
            raise ConnectorError(
                "instagram",
                "capability_restricted",
                "Global public-post keyword search is not available; select hashtag search",
            )
        tag = query.strip().removeprefix("#").strip()
        lookup, _ = await self.request_json(
            "GET",
            f"{self.metadata.base_url}/{self.graph_version}/ig_hashtag_search",
            params={"user_id": self.user_id, "q": tag},
            headers={"Authorization": f"Bearer {self.access_token}"},
            reset_diagnostics=True,
        )
        tags = lookup.get("data", [])
        if not isinstance(tags, list):
            raise ConnectorError(
                "instagram", "invalid_payload", "Instagram returned invalid hashtag data"
            )
        if not tags:
            return []
        hashtag_id = tags[0].get("id")
        params = {
            "user_id": self.user_id,
            "fields": (
                "id,caption,media_type,permalink,timestamp,username,like_count,comments_count"
            ),
            "limit": min(50, limit),
        }
        media: list[dict[str, Any]] = []
        after: str | None = None
        for _page in range(2):
            if after:
                params["after"] = after
            payload, _ = await self.request_json(
                "GET",
                f"{self.metadata.base_url}/{self.graph_version}/{hashtag_id}/recent_media",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                reset_diagnostics=False,
            )
            page = payload.get("data", [])
            if not isinstance(page, list):
                raise ConnectorError(
                    "instagram", "invalid_payload", "Instagram returned invalid media"
                )
            media.extend(page)
            after = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
            if len(media) >= limit or not after or not page:
                break
        return self.normalize_payloads(media[:limit])

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        text = str(payload.get("caption") or "")
        hashtags, mentions = extract_entities(text)
        media_type = str(payload.get("media_type") or "post").lower()
        return ConnectorItem(
            source="instagram",
            external_id=str(payload["id"]),
            canonical_url=str(payload["permalink"]),
            author=payload.get("username"),
            author_handle=payload.get("username"),
            title=None,
            text=text,
            published_at=parse_datetime(payload.get("timestamp")),
            language="und",
            hashtags=hashtags,
            mentions=mentions,
            media_type=media_type,
            raw_metrics=available_metrics(
                payload, {"likes": "like_count", "comments": "comments_count"}
            ),
            raw_metadata={"source_type": "video" if "video" in media_type else "post"},
        )
