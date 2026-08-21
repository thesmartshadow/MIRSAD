from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

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
    exact_query_text,
    parse_datetime,
)
from .social_utils import available_metrics, extract_entities


class RedditConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="reddit",
        name="Reddit",
        kind="social",
        base_url="https://oauth.reddit.com",
        allowed_base_urls=("https://www.reddit.com",),
        requires_credentials=True,
        confidence=65,
        category="social",
        support_level="supported_with_credentials",
        coverage_label="Approved Reddit Data API post search",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            author_search=True,
            recent_search=True,
            historical_search=True,
            date_filter="conditional",
            public_posts=True,
            comments=True,
            engagement_metrics=True,
            pagination=True,
            requires_credentials=True,
            requires_approval=True,
            full_text_search=True,
            identifier_search="conditional",
            content_types=("posts",),
            search_modes=("all_reddit", "communities"),
            sort_modes=("relevance", "recent"),
            acquisition_modes=("DIRECT_API", "WEB_INDEX", "HISTORICAL_INDEX"),
            web_index_search="conditional",
            official_embed="conditional",
            historical_index="conditional",
        ),
    )

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        web_discovery: WebSocialDiscoveryService | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.web_discovery = web_discovery
        if not (client_id and client_secret) and web_discovery and web_discovery.enabled:
            self.metadata = replace(
                type(self).metadata,
                requires_credentials=False,
                support_level="supported",
                coverage_label="Indexed public web coverage; not Reddit Data API search",
                capabilities=replace(
                    type(self).metadata.capabilities,
                    requires_credentials=False,
                    requires_approval=False,
                    engagement_metrics=False,
                    author_search=False,
                    date_filter="conditional",
                    sort_modes=(),
                ),
            )

    def validate_configuration(self) -> tuple[bool, str | None]:
        configured = bool(self.client_id and self.client_secret and self.user_agent)
        if configured:
            return True, "Approved Reddit Data API credentials configured"
        if self.web_discovery and self.web_discovery.enabled:
            return True, "Indexed public web coverage; not Reddit Data API search"
        return False, "Approved API credentials required; local SearXNG discovery is disabled"

    def active_acquisition_mode(self) -> str:
        return (
            AcquisitionMode.DIRECT_API.value
            if self.client_id and self.client_secret and self.user_agent
            else AcquisitionMode.WEB_INDEX.value
        )

    async def validate_access(self) -> ConnectorValidation:
        if not (self.client_id and self.client_secret and self.user_agent):
            if self.web_discovery and self.web_discovery.enabled:
                healthy, code, _latency = await self.web_discovery.validate_access("reddit")
                if healthy:
                    return ConnectorValidation(
                        "pass",
                        "web_index_available",
                        "Indexed public Reddit web discovery available",
                        True,
                    )
                return ConnectorValidation("fail", code, "Local web discovery unavailable", True)
            return await super().validate_access()
        await self._access_token()
        return ConnectorValidation(
            "pass", "credentials_valid", "Reddit OAuth client credentials accepted", True
        )

    async def _access_token(self, *, reset_diagnostics: bool = True) -> str:
        if not (self.client_id and self.client_secret and self.user_agent):
            raise ConnectorError(
                "reddit", "configuration_missing", "Approved API credentials required"
            )
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        payload, _ = await self.request_json(
            "POST",
            "https://www.reddit.com/api/v1/access_token",
            headers={
                "Authorization": f"Basic {credentials}",
                "User-Agent": str(self.user_agent),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            content=urlencode({"grant_type": "client_credentials"}),
            reset_diagnostics=reset_diagnostics,
        )
        token = payload.get("access_token")
        if not token:
            raise ConnectorError(
                "reddit", "invalid_credentials", "Reddit OAuth did not issue a token"
            )
        return str(token)

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
        if not (self.client_id and self.client_secret and self.user_agent):
            return await self._search_web(query, limit=limit, options=options)
        token = await self._access_token()
        source_options = options.for_source("reddit") if options else {}
        communities = [
            value.strip()
            for value in source_options.get("communities", [])
            if isinstance(value, str) and value.strip()
        ][:10]
        endpoint = f"/r/{'+'.join(communities)}/search" if communities else "/search"
        params: dict[str, Any] = {
            "q": exact_query_text(query, bool(options and options.exact_phrase)),
            "sort": "new" if source_options.get("sort") == "recent" else "relevance",
            "limit": min(100, limit),
            "restrict_sr": bool(communities),
            "raw_json": 1,
            "type": "link",
        }
        data: list[dict[str, Any]] = []
        after: str | None = None
        for _page in range(2):
            if after:
                params["after"] = after
            payload, _ = await self.request_json(
                "GET",
                f"{self.metadata.base_url}{endpoint}",
                params=params,
                headers={"Authorization": f"Bearer {token}", "User-Agent": str(self.user_agent)},
                reset_diagnostics=False,
            )
            page = (payload.get("data") or {}).get("children", [])
            if not isinstance(page, list):
                raise ConnectorError(
                    "reddit", "invalid_payload", "Reddit returned an invalid listing"
                )
            data.extend(child.get("data", {}) for child in page if isinstance(child, dict))
            after = (payload.get("data") or {}).get("after")
            if not after or not page:
                break
        if since:
            data = [row for row in data if float(row.get("created_utc") or 0) >= since.timestamp()]
        return self.normalize_payloads(data[:limit])

    async def _search_web(
        self,
        query: str,
        *,
        limit: int,
        options: ConnectorSearchOptions | None,
    ) -> list[ConnectorItem]:
        if not self.web_discovery or not self.web_discovery.enabled:
            raise ConnectorError(
                "reddit",
                "configuration_missing",
                "Approved API credentials required; web discovery disabled",
            )
        source_options = options.for_source("reddit") if options else {}
        try:
            result = await self.web_discovery.search(
                "reddit",
                query,
                limit=limit,
                language=options.language if options else "all",
                time_scope=options.time_range if options else "all",
                exact_phrase=bool(options and options.exact_phrase),
                historical=bool(source_options.get("historical", False)),
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
                "reddit",
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
        title = str(payload.get("title") or "")
        text = str(payload.get("selftext") or title)
        hashtags, mentions = extract_entities(f"{title} {text}")
        permalink = str(payload.get("permalink") or "")
        return ConnectorItem(
            source="reddit",
            external_id=post_id,
            canonical_url=f"https://www.reddit.com{permalink}",
            author=payload.get("author"),
            author_handle=payload.get("author"),
            title=title or None,
            text=text,
            published_at=parse_datetime(payload.get("created_utc")),
            language="und",
            hashtags=hashtags,
            mentions=mentions,
            media_type="post",
            raw_metrics=available_metrics(payload, {"score": "score", "comments": "num_comments"}),
            raw_metadata={
                "source_type": "post",
                "acquisition_mode": AcquisitionMode.DIRECT_API.value,
                "subreddit": payload.get("subreddit"),
                "is_video": payload.get("is_video"),
                "url": payload.get("url"),
                "crosspost_parent": payload.get("crosspost_parent"),
            },
            acquisition_mode=AcquisitionMode.DIRECT_API,
        )
