from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
    exact_query_text,
    parse_datetime,
)
from .social_utils import available_metrics, extract_entities


class XConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="x",
        name="X",
        kind="social",
        base_url="https://api.x.com",
        requires_credentials=True,
        confidence=65,
        category="social",
        support_level="supported_with_credentials",
        coverage_label="Official API recent posts; full archive depends on access tier",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            hashtag_search=True,
            author_search=True,
            recent_search=True,
            historical_search="conditional",
            language_filter=True,
            date_filter=True,
            public_posts=True,
            comments=True,
            engagement_metrics=True,
            pagination=True,
            requires_credentials=True,
            paid_access="conditional",
            full_text_search=True,
            identifier_search="conditional",
            content_types=("posts",),
            sort_modes=("relevance", "recent"),
            acquisition_modes=("DIRECT_API", "WEB_INDEX", "HISTORICAL_INDEX"),
            web_index_search="conditional",
            official_embed="conditional",
            historical_index="conditional",
        ),
    )

    def __init__(
        self,
        bearer_token: str | None = None,
        archive_access: bool = False,
        web_discovery: WebSocialDiscoveryService | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.bearer_token = bearer_token
        self.archive_access = archive_access
        self.web_discovery = web_discovery
        if not bearer_token and web_discovery and web_discovery.enabled:
            self.metadata = replace(
                type(self).metadata,
                requires_credentials=False,
                support_level="supported",
                coverage_label="Indexed public web coverage; not direct X API search",
                capabilities=replace(
                    type(self).metadata.capabilities,
                    requires_credentials=False,
                    paid_access=False,
                    author_search=False,
                    language_filter="conditional",
                    date_filter="conditional",
                ),
            )

    def validate_configuration(self) -> tuple[bool, str | None]:
        if self.bearer_token:
            return True, "Official X API configured"
        if self.web_discovery and self.web_discovery.enabled:
            return True, "Indexed public web coverage; not direct X API search"
        return False, "Bearer token not configured; local SearXNG discovery is disabled"

    def active_acquisition_mode(self) -> str:
        return (
            AcquisitionMode.DIRECT_API.value
            if self.bearer_token
            else AcquisitionMode.WEB_INDEX.value
        )

    async def validate_access(self) -> ConnectorValidation:
        if not self.bearer_token:
            if self.web_discovery and self.web_discovery.enabled:
                healthy, code, _latency = await self.web_discovery.validate_access("x")
                if healthy:
                    return ConnectorValidation(
                        "pass",
                        "web_index_available",
                        "Indexed public X web discovery available",
                        True,
                    )
                return ConnectorValidation("fail", code, "Local web discovery unavailable", True)
            return await super().validate_access()
        await self.request_json(
            "GET",
            f"{self.metadata.base_url}/2/tweets/search/recent",
            params={"query": "open source -is:retweet", "max_results": 10},
            headers={"Authorization": f"Bearer {self.bearer_token}"},
        )
        return ConnectorValidation(
            "pass", "credentials_valid", "Bearer token accepted for recent search", True
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
        if not self.bearer_token:
            return await self._search_web(query, limit=limit, options=options)
        source_options = options.for_source("x") if options else {}
        search_query = exact_query_text(query, bool(options and options.exact_phrase))
        if options and options.language in {"ar", "en"}:
            search_query += f" lang:{options.language}"
        if source_options.get("exclude_reposts", True):
            search_query += " -is:retweet"
        recent_cutoff = datetime.now(UTC) - timedelta(days=7)
        historical = self.archive_access and (
            bool(source_options.get("historical")) or since is None or since < recent_cutoff
        )
        endpoint = "all" if historical else "recent"
        params: dict[str, Any] = {
            "query": search_query,
            "max_results": min(100, max(10, limit)),
            "tweet.fields": (
                "id,text,author_id,created_at,lang,public_metrics,entities,"
                "attachments,referenced_tweets"
            ),
            "expansions": "author_id",
            "user.fields": "id,name,username,verified",
            "sort_order": "recency" if source_options.get("sort") == "recent" else "relevancy",
        }
        if since:
            effective_since = since if historical else max(since, recent_cutoff)
            params["start_time"] = effective_since.isoformat().replace("+00:00", "Z")
        payloads: list[dict[str, Any]] = []
        token: str | None = None
        for _page in range(2):
            if token:
                params["next_token"] = token
            try:
                payload, _ = await self.request_json(
                    "GET",
                    f"{self.metadata.base_url}/2/tweets/search/{endpoint}",
                    params=params,
                    headers={"Authorization": f"Bearer {self.bearer_token}"},
                    reset_diagnostics=_page == 0,
                )
            except ConnectorError as exc:
                if exc.code == "http_403":
                    raise ConnectorError(
                        "x",
                        "access_limited",
                        "Configured X API access does not permit this search",
                        status_code=403,
                    ) from exc
                raise
            users = {
                str(user.get("id")): user
                for user in (payload.get("includes", {}) or {}).get("users", [])
            }
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise ConnectorError("x", "invalid_payload", "X returned an invalid posts payload")
            payloads.extend(
                {**post, "_author": users.get(str(post.get("author_id")), {})} for post in data
            )
            token = (payload.get("meta") or {}).get("next_token")
            if not token or not data:
                break
        return self.normalize_payloads(payloads[:limit])

    async def _search_web(
        self,
        query: str,
        *,
        limit: int,
        options: ConnectorSearchOptions | None,
    ) -> list[ConnectorItem]:
        if not self.web_discovery or not self.web_discovery.enabled:
            raise ConnectorError(
                "x", "configuration_missing", "Bearer token not configured; web discovery disabled"
            )
        source_options = options.for_source("x") if options else {}
        try:
            result = await self.web_discovery.search(
                "x",
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
                "x", exc.code, exc.message, retryable=exc.retryable, status_code=exc.status_code
            ) from exc
        items = self.web_discovery.to_connector_items(result)
        self._set_web_diagnostics(result, len(items))
        return items

    def _set_web_diagnostics(self, result, normalized_count: int) -> None:
        self.last_diagnostics.raw_result_count = result.returned_count
        self.last_diagnostics.fetched_result_count = result.returned_count
        self.last_diagnostics.schema_valid_count = result.target_domain_count
        self.last_diagnostics.query_match_count = normalized_count
        self.last_diagnostics.time_eligible_count = normalized_count
        self.last_diagnostics.normalized_result_count = normalized_count
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
        engine_failures = [item for item in result.telemetry if item.error]
        if engine_failures:
            self.last_diagnostics.warning_code = "partial_engine_failure"
            self.last_diagnostics.warning_message = (
                "Web discovery completed with one or more unavailable search engines"
            )

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        post_id = str(payload["id"])
        text = str(payload.get("text") or "")
        author = payload.get("_author") or {}
        handle = author.get("username")
        entities = payload.get("entities") or {}
        hashtags = (
            tuple(str(tag.get("tag")) for tag in entities.get("hashtags", []) if tag.get("tag"))
            or None
        )
        mentions = (
            tuple(
                str(mention.get("username"))
                for mention in entities.get("mentions", [])
                if mention.get("username")
            )
            or None
        )
        if hashtags is None or mentions is None:
            extracted_tags, extracted_mentions = extract_entities(text)
            hashtags = hashtags or extracted_tags
            mentions = mentions or extracted_mentions
        metrics = available_metrics(
            payload.get("public_metrics") or {},
            {
                "likes": "like_count",
                "reposts": "retweet_count",
                "replies": "reply_count",
                "quotes": "quote_count",
                "views": "impression_count",
            },
        )
        return ConnectorItem(
            source="x",
            external_id=post_id,
            canonical_url=f"https://x.com/{handle or 'i'}/status/{post_id}",
            author=author.get("name") or handle,
            author_handle=handle,
            author_verified=author.get("verified") if "verified" in author else None,
            title=None,
            text=text,
            published_at=parse_datetime(payload.get("created_at")),
            language=str(payload.get("lang") or "und"),
            hashtags=hashtags,
            mentions=mentions,
            media_type="post",
            raw_metrics=metrics,
            raw_metadata={
                "source_type": "post",
                "acquisition_mode": AcquisitionMode.DIRECT_API.value,
                "referenced_tweets": payload.get("referenced_tweets"),
                "attachments": payload.get("attachments"),
            },
            acquisition_mode=AcquisitionMode.DIRECT_API,
        )
