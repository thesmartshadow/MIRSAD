from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorValidation,
    parse_datetime,
)
from .social_utils import available_metrics


class TikTokConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="tiktok",
        name="TikTok",
        kind="social",
        base_url="https://open.tiktokapis.com",
        requires_credentials=True,
        confidence=60,
        category="social",
        support_level="restricted_access",
        coverage_label="Public videos through the approved Research API",
        capabilities=ConnectorCapabilities(
            keyword_search="conditional",
            phrase_search="conditional",
            hashtag_search="conditional",
            author_search=True,
            recent_search=True,
            historical_search=True,
            language_filter=False,
            date_filter=True,
            public_posts=True,
            comments="conditional",
            engagement_metrics=True,
            pagination=True,
            requires_credentials=True,
            requires_approval=True,
            content_types=("videos",),
        ),
    )

    def __init__(
        self,
        client_key: str | None = None,
        client_secret: str | None = None,
        research_approved: bool = False,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.client_key = client_key
        self.client_secret = client_secret
        self.research_approved = research_approved

    def configuration_state(self) -> str:
        return "configured" if self.validate_configuration()[0] else "restricted"

    def validate_configuration(self) -> tuple[bool, str | None]:
        configured = bool(self.research_approved and self.client_key and self.client_secret)
        return configured, None if configured else "Research API approval and credentials required"

    async def validate_access(self) -> ConnectorValidation:
        if not self.validate_configuration()[0]:
            return await super().validate_access()
        await self._token()
        return ConnectorValidation(
            "pass", "credentials_valid", "Research API client credentials accepted", True
        )

    async def _token(self, *, reset_diagnostics: bool = True) -> str:
        if not self.validate_configuration()[0]:
            raise ConnectorError("tiktok", "restricted_access", "Research API approval required")
        payload, _ = await self.request_json(
            "POST",
            f"{self.metadata.base_url}/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content=urlencode(
                {
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                }
            ),
            reset_diagnostics=reset_diagnostics,
        )
        token = payload.get("access_token")
        if not token:
            raise ConnectorError("tiktok", "invalid_credentials", "TikTok did not issue a token")
        return str(token)

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        token = await self._token()
        end = datetime.now(UTC)
        start = max(since or end - timedelta(days=30), end - timedelta(days=30))
        body: dict[str, Any] = {
            "query": {
                "and": [{"operation": "EQ", "field_name": "keyword", "field_values": [query]}]
            },
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
            "max_count": min(100, limit),
            "is_random": False,
        }
        fields = (
            "id,video_description,create_time,region_code,share_count,view_count,"
            "like_count,comment_count,hashtag_names,username,favorites_count,video_duration"
        )
        videos: list[dict[str, Any]] = []
        for _page in range(2):
            payload, _ = await self.request_json(
                "POST",
                f"{self.metadata.base_url}/v2/research/video/query/",
                params={"fields": fields},
                headers={"Authorization": f"Bearer {token}"},
                json_body=body,
                reset_diagnostics=False,
            )
            data = payload.get("data") or {}
            page = data.get("videos", [])
            if not isinstance(page, list):
                raise ConnectorError(
                    "tiktok", "invalid_payload", "TikTok returned invalid video data"
                )
            videos.extend(page)
            if len(videos) >= limit or not data.get("has_more") or not page:
                break
            body["cursor"] = data.get("cursor")
            if data.get("search_id"):
                body["search_id"] = data["search_id"]
        return self.normalize_payloads(videos[:limit])

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        video_id = str(payload["id"])
        username = payload.get("username")
        return ConnectorItem(
            source="tiktok",
            external_id=video_id,
            canonical_url=f"https://www.tiktok.com/@{username or 'user'}/video/{video_id}",
            author=username,
            author_handle=username,
            title=None,
            text=str(payload.get("video_description") or ""),
            published_at=parse_datetime(payload.get("create_time")),
            language="und",
            hashtags=tuple(payload.get("hashtag_names") or []) or None,
            mentions=tuple(payload.get("video_mention_list") or []) or None,
            media_type="video",
            raw_metrics=available_metrics(
                payload,
                {
                    "views": "view_count",
                    "likes": "like_count",
                    "comments": "comment_count",
                    "shares": "share_count",
                    "favorites": "favorites_count",
                },
            ),
            raw_metadata={
                "source_type": "video",
                "region": payload.get("region_code"),
                "duration": payload.get("video_duration"),
            },
        )
