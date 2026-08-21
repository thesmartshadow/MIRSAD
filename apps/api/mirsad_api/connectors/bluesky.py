from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..provenance import AcquisitionMode
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


class BlueskyConnector(BaseConnector):
    PRIMARY_APPVIEW = "https://api.bsky.app"
    SECONDARY_APPVIEW = "https://public.api.bsky.app"

    metadata = ConnectorMetadata(
        key="bluesky",
        name="Bluesky",
        kind="social",
        base_url=PRIMARY_APPVIEW,
        confidence=65,
        category="social",
        coverage_label="Public posts indexed by Bluesky",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            hashtag_search=True,
            author_search=True,
            recent_search=True,
            historical_search="conditional",
            language_filter=True,
            date_filter="conditional",
            public_posts=True,
            engagement_metrics=True,
            pagination=True,
            full_text_search=True,
            identifier_search="conditional",
            content_types=("posts",),
            sort_modes=("top", "recent"),
            acquisition_modes=("PUBLIC_API",),
        ),
        allowed_base_urls=(SECONDARY_APPVIEW,),
    )

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def validate_access(self) -> ConnectorValidation:
        await self._request_search(
            {"q": "open source", "limit": 1, "sort": "latest"},
            reset_diagnostics=True,
        )
        return ConnectorValidation(
            "pass",
            "public_appview_search_available",
            "Public AppView search available",
            True,
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            validation = await self.validate_access()
            return {
                "status": "healthy",
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
        params: dict[str, Any] = {"q": query, "limit": min(limit, 100), "sort": "latest"}
        if since:
            params["since"] = since.isoformat()
        return await self._collect(params, limit=limit)

    async def search_with_options(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None = None,
        options: ConnectorSearchOptions | None = None,
    ) -> list[ConnectorItem]:
        source_options = options.for_source(self.metadata.key) if options else {}
        params: dict[str, Any] = {
            "q": exact_query_text(query, bool(options and options.exact_phrase)),
            "limit": min(limit, 100),
            "sort": "latest" if source_options.get("sort") == "recent" else "top",
        }
        if options and options.language in {"ar", "en"}:
            params["lang"] = options.language
        if since:
            params["since"] = since.isoformat()
        return await self._collect(params, limit=limit)

    async def _collect(self, params: dict[str, Any], *, limit: int) -> list[ConnectorItem]:
        posts: list[dict[str, Any]] = []
        endpoint: str | None = None
        cursor: str | None = None
        malformed_container_items = 0
        for page_number in range(2):
            remaining = max(0, min(limit, 200) - len(posts))
            if remaining == 0:
                break
            page_params = {**params, "limit": min(100, remaining)}
            if cursor:
                page_params["cursor"] = cursor
            try:
                payload, endpoint = await self._request_search(
                    page_params,
                    reset_diagnostics=page_number == 0,
                    endpoint=endpoint,
                )
            except ConnectorError as error:
                if not posts:
                    raise
                self.last_diagnostics.warning_code = error.code
                self.last_diagnostics.warning_message = (
                    "Bluesky returned an earlier page but a later page was unavailable"
                )
                self.last_diagnostics.warning_status_code = error.status_code
                self.last_diagnostics.details["partial_page_failure"] = error.code
                break
            page = payload.get("posts")
            if not isinstance(page, list):
                raise ConnectorError(
                    self.metadata.key,
                    "invalid_payload",
                    "Bluesky returned an invalid posts payload",
                )
            posts.extend(item for item in page if isinstance(item, dict))
            malformed_container_items += sum(not isinstance(item, dict) for item in page)
            cursor_value = payload.get("cursor")
            cursor = cursor_value if isinstance(cursor_value, str) and cursor_value else None
            if not cursor:
                break
        items = self.normalize_payloads(posts[:limit])
        self.last_diagnostics.malformed_count += malformed_container_items
        self.last_diagnostics.details.update(
            {
                "mode": "PUBLIC_APPVIEW_SEARCH",
                "endpoint": endpoint,
                "authenticated": False,
            }
        )
        return items

    async def _request_search(
        self,
        params: dict[str, Any],
        *,
        reset_diagnostics: bool,
        endpoint: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        candidates = (
            (self.PRIMARY_APPVIEW, self.SECONDARY_APPVIEW)
            if endpoint in {None, self.PRIMARY_APPVIEW}
            else (self.SECONDARY_APPVIEW,)
        )
        first_error: ConnectorError | None = None
        for index, base_url in enumerate(candidates):
            if base_url is None:
                continue
            try:
                payload, _ = await self.request_json(
                    "GET",
                    f"{base_url}/xrpc/app.bsky.feed.searchPosts",
                    params=params,
                    reset_diagnostics=reset_diagnostics and index == 0,
                )
                if not isinstance(payload, dict):
                    raise ConnectorError(
                        self.metadata.key,
                        "invalid_payload",
                        "Bluesky returned an invalid search payload",
                    )
                if first_error:
                    self.last_diagnostics.details["primary_endpoint_error"] = first_error.code
                return payload, base_url
            except ConnectorError as error:
                if index > 0:
                    if first_error:
                        self.last_diagnostics.details["primary_endpoint_error"] = first_error.code
                    raise
                if error.code not in {
                    "http_403",
                    "timeout",
                    "dns_network",
                    "upstream_5xx",
                }:
                    raise
                first_error = error
        if first_error:
            raise first_error
        raise ConnectorError(
            self.metadata.key, "unavailable", "No Bluesky AppView endpoint is available"
        )

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        author = payload.get("author") or {}
        record = payload.get("record") or {}
        uri = str(payload.get("uri", ""))
        parts = uri.split("/")
        post_id = parts[-1] if parts else str(payload.get("cid", "unknown"))
        handle = author.get("handle") or author.get("did", "unknown")
        embed = payload.get("embed") or {}
        external = embed.get("external") or {}
        text = str(record.get("text") or external.get("description") or "")
        return ConnectorItem(
            source=self.metadata.key,
            external_id=uri or str(payload.get("cid", post_id)),
            canonical_url=f"https://bsky.app/profile/{handle}/post/{post_id}",
            author=author.get("displayName") or handle,
            title=external.get("title"),
            text=text,
            published_at=parse_datetime(record.get("createdAt") or payload.get("indexedAt")),
            language=(record.get("langs") or ["und"])[0],
            author_handle=str(handle),
            author_verified=None,
            hashtags=tuple(
                feature["tag"]
                for facet in record.get("facets", [])
                for feature in facet.get("features", [])
                if isinstance(feature, dict) and feature.get("tag")
            )
            or None,
            mentions=None,
            media_type="post",
            raw_metrics={
                key: payload[field]
                for key, field in (
                    ("likes", "likeCount"),
                    ("reposts", "repostCount"),
                    ("replies", "replyCount"),
                    ("quotes", "quoteCount"),
                )
                if field in payload
            },
            raw_metadata={
                "uri": uri,
                "cid": payload.get("cid"),
                "handle": handle,
                "source_type": "post",
                "quoted_post": (payload.get("embed") or {}).get("record"),
                "acquisition_mode": AcquisitionMode.PUBLIC_API.value,
            },
            acquisition_mode=AcquisitionMode.PUBLIC_API,
        )
