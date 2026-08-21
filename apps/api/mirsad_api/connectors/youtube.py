from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorSearchOptions,
    ConnectorValidation,
    exact_query_text,
    parse_datetime,
)
from .social_utils import available_metrics, extract_entities


class YouTubeConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="youtube",
        name="YouTube",
        kind="video",
        base_url="https://www.googleapis.com",
        requires_credentials=True,
        confidence=70,
        category="social",
        support_level="supported_with_credentials",
        coverage_label="Public videos, channels, and playlists through YouTube Data API",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            hashtag_search=True,
            author_search="conditional",
            recent_search=True,
            historical_search=True,
            language_filter=True,
            date_filter=True,
            public_posts=True,
            comments="conditional",
            engagement_metrics=True,
            pagination=True,
            requires_credentials=True,
            full_text_search=True,
            identifier_search="conditional",
            content_types=("videos", "channels", "playlists"),
            sort_modes=("relevance", "recent", "most_engaged"),
            acquisition_modes=("DIRECT_API",),
        ),
    )

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key

    def validate_configuration(self) -> tuple[bool, str | None]:
        return (bool(self.api_key), None if self.api_key else "API key not configured")

    async def validate_access(self) -> ConnectorValidation:
        if not self.api_key:
            return await super().validate_access()
        await self.request_json(
            "GET",
            f"{self.metadata.base_url}/youtube/v3/i18nLanguages",
            params={"part": "snippet", "hl": "en"},
            headers={"X-Goog-Api-Key": str(self.api_key)},
        )
        return ConnectorValidation(
            "pass", "credentials_valid", "API key accepted by YouTube Data API", True
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            validation = await self.validate_access()
            return {
                "status": "healthy" if validation.state == "pass" else validation.code,
                "detail": validation.message,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        except ConnectorError as error:
            return {
                "status": "rate_limited" if error.code == "rate_limited" else "unavailable",
                "detail": error.message,
                "checked_at": datetime.now(UTC).isoformat(),
            }

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        return await self.search_with_options(query, limit=limit, since=since)

    async def search_with_options(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None = None,
        options: ConnectorSearchOptions | None = None,
    ) -> list[ConnectorItem]:
        configured, reason = self.validate_configuration()
        if not configured:
            raise ConnectorError(self.metadata.key, "unconfigured", reason or "Not configured")
        source_options = options.for_source("youtube") if options else {}
        requested_types = source_options.get("types", ["video", "channel", "playlist"])
        valid_types = [
            value for value in requested_types if value in {"video", "channel", "playlist"}
        ]
        selected_types = valid_types or ["video", "channel", "playlist"]
        sort = source_options.get("sort")
        params: dict[str, Any] = {
            "part": "snippet",
            "type": ",".join(selected_types),
            "q": exact_query_text(query, bool(options and options.exact_phrase)),
            "maxResults": min(limit, 50),
            "order": "date"
            if sort == "recent"
            else "viewCount"
            if sort == "most_engaged"
            else "relevance",
        }
        headers = {"X-Goog-Api-Key": str(self.api_key)}
        if options and options.language in {"ar", "en"}:
            params["relevanceLanguage"] = options.language
        if region := source_options.get("region"):
            params["regionCode"] = str(region).upper()[:2]
        if since:
            params["publishedAfter"] = since.isoformat()
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        for _ in range(2):  # At most two quota-bearing search calls per MIRSAD search.
            if page_token:
                params["pageToken"] = page_token
            try:
                payload, _latency = await self.request_json(
                    "GET",
                    f"{self.metadata.base_url}/youtube/v3/search",
                    params=params,
                    headers=headers,
                    reset_diagnostics=page_token is None,
                )
            except ConnectorError as exc:
                if exc.status_code == 403:
                    raise ConnectorError(
                        "youtube",
                        "quota_exhausted",
                        "YouTube quota is exhausted or access is not permitted",
                        status_code=403,
                    ) from exc
                raise
            page = payload.get("items", [])
            if not isinstance(page, list):
                raise ConnectorError(
                    "youtube", "invalid_payload", "YouTube returned invalid search data"
                )
            items.extend(page)
            page_token = payload.get("nextPageToken")
            if len(items) >= limit or not page_token or not page:
                break
        items = items[:limit]
        ids = [item.get("id", {}).get("videoId") for item in items]
        ids = [str(video_id) for video_id in ids if video_id]
        metrics: dict[str, dict[str, Any]] = {}
        if ids:
            details, _ = await self.request_json(
                "GET",
                f"{self.metadata.base_url}/youtube/v3/videos",
                params={"part": "statistics", "id": ",".join(ids)},
                headers=headers,
                reset_diagnostics=False,
            )
            details_items = details.get("items", [])
            if not isinstance(details_items, list):
                raise ConnectorError(
                    "youtube", "invalid_payload", "YouTube returned invalid statistics"
                )
            metrics = {item["id"]: item.get("statistics", {}) for item in details_items}
        payloads = [
            {**item, "statistics": metrics.get(item.get("id", {}).get("videoId"), {})}
            for item in items
        ]
        return self.normalize_payloads(payloads)

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        identifier = payload.get("id") or {}
        source_type, external_id, canonical_url = self._identity(identifier)
        snippet = payload.get("snippet") or {}
        statistics = payload.get("statistics") or {}
        text = str(snippet.get("description") or snippet.get("title") or "")
        hashtags, mentions = extract_entities(text)
        return ConnectorItem(
            source=self.metadata.key,
            external_id=external_id,
            canonical_url=canonical_url,
            author=snippet.get("channelTitle"),
            author_handle=None,
            title=snippet.get("title"),
            text=text,
            published_at=parse_datetime(snippet.get("publishedAt")),
            language="und",
            hashtags=hashtags,
            mentions=mentions,
            media_type=source_type,
            raw_metrics=available_metrics(
                statistics,
                {"views": "viewCount", "likes": "likeCount", "comments": "commentCount"},
            ),
            raw_metadata={"source_type": source_type, "channel_id": snippet.get("channelId")},
        )

    @staticmethod
    def _identity(identifier: dict[str, Any]) -> tuple[str, str, str]:
        if identifier.get("videoId"):
            value = str(identifier["videoId"])
            return "video", value, f"https://www.youtube.com/watch?v={value}"
        if identifier.get("channelId"):
            value = str(identifier["channelId"])
            return "channel", value, f"https://www.youtube.com/channel/{value}"
        if identifier.get("playlistId"):
            value = str(identifier["playlistId"])
            return "playlist", value, f"https://www.youtube.com/playlist?list={value}"
        raise ValueError("YouTube result is missing a supported object identifier")
