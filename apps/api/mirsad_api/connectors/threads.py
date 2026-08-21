from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from ..discovery.searxng import DiscoveryProviderError
from ..discovery.service import WebSocialDiscoveryService
from ..provenance import AcquisitionMode
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


class ThreadsConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="threads",
        name="Threads",
        kind="social",
        base_url="https://graph.threads.net",
        requires_credentials=True,
        confidence=65,
        category="social",
        support_level="supported_with_credentials",
        coverage_label="Official Threads keyword and topic-tag search",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            hashtag_search=True,
            recent_search=True,
            historical_search=False,
            date_filter=True,
            public_posts=True,
            comments="conditional",
            engagement_metrics="conditional",
            pagination=True,
            requires_credentials=True,
            requires_approval=True,
            full_text_search=True,
            identifier_search="conditional",
            content_types=("posts",),
            search_modes=("keyword", "topic_tag"),
            sort_modes=("top", "recent"),
            acquisition_modes=("DIRECT_API", "WEB_INDEX"),
            web_index_search="conditional",
            official_embed=False,
        ),
    )

    def __init__(
        self,
        access_token: str | None = None,
        web_discovery: WebSocialDiscoveryService | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.access_token = access_token
        self.web_discovery = web_discovery
        if not access_token and web_discovery and web_discovery.enabled:
            self.metadata = replace(
                type(self).metadata,
                requires_credentials=False,
                support_level="supported",
                coverage_label="Indexed public web coverage; not Threads API search",
                capabilities=replace(
                    type(self).metadata.capabilities,
                    requires_credentials=False,
                    requires_approval=False,
                    comments=False,
                    engagement_metrics=False,
                    date_filter="conditional",
                    sort_modes=(),
                ),
            )

    def validate_configuration(self) -> tuple[bool, str | None]:
        if self.access_token:
            return True, "Official Threads API configured"
        if self.web_discovery and self.web_discovery.enabled:
            return True, "Indexed public web coverage; not Threads API search"
        return False, "Access token not configured; local SearXNG discovery is disabled"

    def active_acquisition_mode(self) -> str:
        return (
            AcquisitionMode.DIRECT_API.value
            if self.access_token
            else AcquisitionMode.WEB_INDEX.value
        )

    async def validate_access(self) -> ConnectorValidation:
        if not self.access_token:
            if self.web_discovery and self.web_discovery.enabled:
                healthy, code, _latency = await self.web_discovery.validate_access("threads")
                if healthy:
                    return ConnectorValidation(
                        "pass",
                        "web_index_available",
                        "Indexed public Threads web discovery available",
                        True,
                    )
                return ConnectorValidation("fail", code, "Local web discovery unavailable", True)
            return await super().validate_access()
        await self.request_json(
            "GET",
            f"{self.metadata.base_url}/me",
            params={"fields": "id"},
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        return ConnectorValidation(
            "pass", "credentials_valid", "Threads user access token accepted", True
        )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        return await self.search_with_options(query, limit=limit, since=since)

    async def search_with_options(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None = None,
        options: ConnectorSearchOptions | None = None,
    ) -> list[ConnectorItem]:
        if not self.access_token:
            return await self._search_web(query, limit=limit, options=options)
        source_options = options.for_source("threads") if options else {}
        params: dict[str, Any] = {
            "q": query,
            "search_type": str(source_options.get("sort", "TOP")).upper(),
            "search_mode": "TAG" if source_options.get("mode") == "topic_tag" else "KEYWORD",
            "limit": min(100, limit),
            "fields": (
                "id,media_type,permalink,username,text,timestamp,is_quote_post,"
                "quoted_post,reposted_post,has_replies,link_attachment_url"
            ),
        }
        if since:
            params["since"] = int(since.timestamp())
        posts: list[dict[str, Any]] = []
        after: str | None = None
        for _page in range(2):
            if after:
                params["after"] = after
            payload, _ = await self.request_json(
                "GET",
                f"{self.metadata.base_url}/keyword_search",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                reset_diagnostics=_page == 0,
            )
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise ConnectorError(
                    "threads", "invalid_payload", "Threads returned an invalid posts payload"
                )
            posts.extend(data)
            after = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
            if len(posts) >= limit or not after or not data:
                break
        return self.normalize_payloads(posts[:limit])

    async def _search_web(
        self,
        query: str,
        *,
        limit: int,
        options: ConnectorSearchOptions | None,
    ) -> list[ConnectorItem]:
        if not self.web_discovery or not self.web_discovery.enabled:
            raise ConnectorError(
                "threads",
                "configuration_missing",
                "Access token not configured; web discovery disabled",
            )
        try:
            result = await self.web_discovery.search(
                "threads",
                query,
                limit=limit,
                language=options.language if options else "all",
                time_scope=options.time_range if options else "all",
                exact_phrase=bool(options and options.exact_phrase),
                historical=False,
                original_query=options.original_query if options else query,
                query_variants=options.query_variants if options else (),
                query_variant_metadata=(options.query_variant_metadata if options else ()),
                search_round=options.search_round if options else 1,
                max_engine_calls=options.max_discovery_engine_calls if options else 0,
                max_discovered_urls=options.max_discovered_urls if options else 0,
                max_historical_calls=options.max_historical_calls if options else 0,
            )
        except DiscoveryProviderError as exc:
            raise ConnectorError(
                "threads",
                exc.code,
                exc.message,
                retryable=exc.retryable,
                status_code=exc.status_code,
            ) from exc
        items = self.web_discovery.to_connector_items(result)
        self.last_diagnostics.raw_result_count = result.returned_count
        self.last_diagnostics.fetched_result_count = result.returned_count
        self.last_diagnostics.schema_valid_count = result.target_domain_count
        self.last_diagnostics.query_match_count = len(items)
        self.last_diagnostics.time_eligible_count = len(items)
        self.last_diagnostics.normalized_result_count = len(items)
        self.last_diagnostics.malformed_count = 0
        self.last_diagnostics.total_latency_ms = result.total_latency_ms
        self.last_diagnostics.http_status = (
            200 if result.cache_state in {"fresh", "refreshed"} else None
        )
        self.last_diagnostics.details = result.diagnostics()
        self.last_diagnostics.details["acquisition_mode"] = AcquisitionMode.WEB_INDEX.value
        self.last_diagnostics.details["wrong_domain_rejected"] = max(
            0, result.returned_count - result.target_domain_count
        )
        if any(item.error for item in result.telemetry):
            self.last_diagnostics.warning_code = "partial_engine_failure"
            self.last_diagnostics.warning_message = (
                "Web discovery completed with one or more unavailable search engines"
            )
        return items

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        post_id = str(payload["id"])
        text = str(payload.get("text") or "")
        hashtags, mentions = extract_entities(text)
        insights = payload.get("public_metrics") or payload.get("insights") or {}
        return ConnectorItem(
            source="threads",
            external_id=post_id,
            canonical_url=str(
                payload.get("permalink") or f"https://www.threads.net/post/{post_id}"
            ),
            author=payload.get("username"),
            author_handle=payload.get("username"),
            author_verified=payload.get("is_verified") if "is_verified" in payload else None,
            title=None,
            text=text,
            published_at=parse_datetime(payload.get("timestamp")),
            language=str(payload.get("language") or "und"),
            hashtags=hashtags,
            mentions=mentions,
            media_type=str(payload.get("media_type") or "post").lower(),
            raw_metrics=available_metrics(
                insights,
                {
                    "likes": "like_count",
                    "replies": "reply_count",
                    "reposts": "repost_count",
                    "quotes": "quote_count",
                },
            ),
            raw_metadata={
                "source_type": "post",
                "acquisition_mode": AcquisitionMode.DIRECT_API.value,
                "is_quote_post": payload.get("is_quote_post"),
                "quoted_post": payload.get("quoted_post"),
                "reposted_post": payload.get("reposted_post"),
                "link_attachment_url": payload.get("link_attachment_url"),
            },
            acquisition_mode=AcquisitionMode.DIRECT_API,
        )
