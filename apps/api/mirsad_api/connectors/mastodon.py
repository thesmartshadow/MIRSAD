from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import quote, urlsplit

from ..domains.query import normalize_text, process_query, tokenize
from ..provenance import AcquisitionMode
from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorSearchOptions,
    ConnectorValidation,
    parse_datetime,
)
from .social_utils import available_metrics, plain_text

PUBLIC_MODE = "PUBLIC_TIMELINE"
HASHTAG_MODE = "HASHTAG_TIMELINE"
AUTHENTICATED_MODE = "AUTHENTICATED_FULLTEXT_SEARCH"


@dataclass(frozen=True, slots=True)
class _InstanceCollection:
    instance: str
    statuses: tuple[dict[str, Any], ...]
    diagnostics: ConnectorDiagnostics
    fetched_count: int
    malformed_count: int
    error: ConnectorError | None = None


def _normalized_instance(value: str | None) -> str | None:
    candidate = (value or "").strip().rstrip("/")
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return None
    return f"https://{parsed.netloc}"


class MastodonConnector(BaseConnector):
    def __init__(
        self,
        instance_url: str | None = None,
        access_token: str | None = None,
        public_instances: list[str] | tuple[str, ...] | None = None,
        public_pages: int = 1,
        public_records_per_instance: int = 40,
        instance_concurrency: int = 3,
        **kwargs: Any,
    ) -> None:
        self.instance_url = _normalized_instance(instance_url) or ""
        self.access_token = access_token
        configured_public = public_instances if public_instances is not None else ["https://mas.to"]
        normalized_public = [_normalized_instance(value) for value in configured_public[:4]]
        self.public_instances = tuple(dict.fromkeys(value for value in normalized_public if value))
        self.invalid_public_instances = sum(value is None for value in normalized_public)
        self.public_pages = max(1, min(public_pages, 2))
        self.public_records_per_instance = max(1, min(public_records_per_instance, 80))
        self.instance_concurrency = max(1, min(instance_concurrency, 4))
        base_url = self.instance_url or next(iter(self.public_instances), "https://invalid.local")
        allowed_urls = tuple(
            value
            for value in (self.instance_url, *self.public_instances)
            if value and value != base_url
        )
        self.metadata = ConnectorMetadata(
            key="mastodon",
            name="Mastodon",
            kind="social",
            base_url=base_url,
            requires_credentials=False,
            confidence=62,
            category="social",
            support_level="supported",
            coverage_label="Public timeline coverage on configured Mastodon instances",
            capabilities=ConnectorCapabilities(
                keyword_search="conditional",
                phrase_search="conditional",
                hashtag_search=True,
                author_search="conditional",
                recent_search=True,
                historical_search=False,
                language_filter=False,
                date_filter="conditional",
                public_posts=True,
                engagement_metrics=True,
                pagination=True,
                requires_credentials=False,
                public_timeline=True,
                hashtag_timeline=True,
                authenticated_fulltext_search="conditional",
                instance_scoped=True,
                full_text_search="conditional",
                identifier_search="conditional",
                content_types=("posts",),
                search_modes=(
                    "public_timeline",
                    "hashtag_timeline",
                    "authenticated_fulltext_search",
                ),
                acquisition_modes=("DIRECT_API", "PUBLIC_TIMELINE"),
            ),
            allowed_base_urls=allowed_urls,
        )
        super().__init__(**kwargs)

    @property
    def authenticated_configured(self) -> bool:
        return bool(self.instance_url and self.access_token)

    def active_acquisition_mode(self) -> str:
        return (
            AcquisitionMode.DIRECT_API.value
            if self.authenticated_configured
            else AcquisitionMode.PUBLIC_TIMELINE.value
        )

    def validate_configuration(self) -> tuple[bool, str | None]:
        if self.authenticated_configured:
            return True, "Authenticated full-text search configured"
        if self.public_instances:
            return True, "Public timeline mode; full-text search not configured"
        if self.invalid_public_instances:
            return False, "Mastodon public instances must be valid HTTPS origins"
        return False, "No server-configured Mastodon public instances"

    async def validate_access(self) -> ConnectorValidation:
        if self.authenticated_configured:
            await self.request_json(
                "GET",
                f"{self.instance_url}/api/v1/accounts/verify_credentials",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            self.last_diagnostics.details = {
                "mode": AUTHENTICATED_MODE,
                "instances": [self.instance_url],
            }
            return ConnectorValidation(
                "pass", "credentials_valid", "Mastodon user access token accepted", True
            )
        if not self.public_instances:
            return await super().validate_access()
        started = perf_counter()
        results = await self._fetch_public_instances(page_limit=1, pages=1)
        self._aggregate_diagnostics(results, started=started, mode=PUBLIC_MODE)
        successful = [result for result in results if result.error is None]
        if successful:
            return ConnectorValidation(
                "pass",
                "public_timeline_available",
                "Public timeline mode; full-text search not configured",
                True,
            )
        errors = [result.error for result in results if result.error is not None]
        if errors and all(error.code == "auth_required" for error in errors):
            return ConnectorValidation(
                "warn",
                "auth_required",
                "Configured Mastodon instances require authentication for public timelines",
                True,
            )
        if errors:
            raise errors[0]
        raise ConnectorError("mastodon", "unavailable", "No Mastodon instance was available")

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
        if self.authenticated_configured:
            try:
                return await self._authenticated_search(query, limit=limit, since=since)
            except ConnectorError as error:
                if not self.public_instances or error.code not in {
                    "http_401",
                    "http_403",
                    "http_404",
                    "access_limited",
                }:
                    raise
        if not self.public_instances:
            raise ConnectorError(
                "mastodon",
                "configuration_missing",
                "No server-configured Mastodon public instances",
            )
        exact_phrase = bool(options and options.exact_phrase)
        return await self._public_search(
            query,
            limit=limit,
            since=since,
            exact_phrase=exact_phrase,
        )

    async def _authenticated_search(
        self, query: str, *, limit: int, since: datetime | None
    ) -> list[ConnectorItem]:
        params: dict[str, Any] = {
            "q": query,
            "type": "statuses",
            "limit": min(40, limit),
            "resolve": False,
        }
        statuses: list[dict[str, Any]] = []
        for page_number in range(2):
            if page_number:
                params["offset"] = len(statuses)
            payload, _ = await self.request_json(
                "GET",
                f"{self.instance_url}/api/v2/search",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                reset_diagnostics=page_number == 0,
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("statuses"), list):
                raise ConnectorError(
                    "mastodon", "invalid_payload", "Mastodon returned invalid statuses"
                )
            page = payload["statuses"]
            statuses.extend(
                {**row, "_mirsad_instance": self.instance_url}
                for row in page
                if isinstance(row, dict)
            )
            if len(statuses) >= limit or not page or len(page) < params["limit"]:
                break
        if since:
            statuses = [
                row for row in statuses if (parse_datetime(row.get("created_at")) or since) >= since
            ]
        items = self.normalize_payloads(statuses[:limit])
        self.last_diagnostics.details = {
            "mode": AUTHENTICATED_MODE,
            "instances": [self.instance_url],
            "local_query_matches": len(items),
            "duplicates": 0,
        }
        return items

    async def _public_search(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None,
        exact_phrase: bool,
    ) -> list[ConnectorItem]:
        processed = process_query(query, exact_phrase=exact_phrase)
        hashtag = (
            processed.tokens[0] if processed.intent == "hashtag" and processed.tokens else None
        )
        mode = HASHTAG_MODE if hashtag else PUBLIC_MODE
        started = perf_counter()
        results = await self._fetch_public_instances(
            hashtag=hashtag,
            page_limit=min(40, self.public_records_per_instance),
            pages=self.public_pages,
        )
        self._aggregate_diagnostics(results, started=started, mode=mode)
        successful = [result for result in results if result.error is None]
        if not successful:
            errors = [result.error for result in results if result.error is not None]
            if errors:
                raise errors[0]
            raise ConnectorError("mastodon", "unavailable", "No Mastodon instance was available")

        matched: list[ConnectorItem] = []
        schema_valid = 0
        query_matches = 0
        time_eligible = 0
        malformed = sum(result.malformed_count for result in successful)
        for result in successful:
            for payload in result.statuses:
                try:
                    item = self.normalize(
                        {
                            **payload,
                            "_mirsad_instance": result.instance,
                            "_mirsad_mode": mode,
                        }
                    )
                except (KeyError, TypeError, ValueError, OverflowError):
                    malformed += 1
                    continue
                if not self._valid_item(item):
                    malformed += 1
                    continue
                schema_valid += 1
                if not self._matches_query(item, processed.normalized, exact_phrase=exact_phrase):
                    continue
                query_matches += 1
                if since and item.published_at and item.published_at < since:
                    continue
                time_eligible += 1
                matched.append(item)

        unique, duplicate_count = self._deduplicate_federated(matched)
        unique.sort(
            key=lambda item: (
                item.published_at or datetime.min.replace(tzinfo=UTC),
                item.canonical_url,
                item.external_id,
            ),
            reverse=True,
        )
        output = unique[:limit]
        diagnostics = self.last_diagnostics
        diagnostics.raw_result_count = sum(result.fetched_count for result in successful)
        diagnostics.fetched_result_count = diagnostics.raw_result_count
        diagnostics.schema_valid_count = schema_valid
        diagnostics.query_match_count = query_matches
        diagnostics.time_eligible_count = time_eligible
        diagnostics.normalized_result_count = len(output)
        diagnostics.malformed_count = malformed
        diagnostics.query_excluded_count = max(0, schema_valid - query_matches)
        diagnostics.time_excluded_count = max(0, query_matches - time_eligible)
        diagnostics.details.update(
            {
                "mode": mode,
                "instances": list(self.public_instances),
                "local_query_matches": query_matches,
                "duplicates": duplicate_count,
                "bounded_pages_per_instance": self.public_pages,
                "bounded_records_per_instance": self.public_records_per_instance,
            }
        )
        failures = [result for result in results if result.error is not None]
        if failures:
            diagnostics.warning_code = failures[0].error.code
            diagnostics.warning_message = (
                "One or more configured Mastodon instances could not be collected"
            )
            diagnostics.warning_status_code = failures[0].error.status_code
        return output

    async def _fetch_public_instances(
        self,
        *,
        hashtag: str | None = None,
        page_limit: int,
        pages: int,
    ) -> list[_InstanceCollection]:
        semaphore = asyncio.Semaphore(self.instance_concurrency)

        async def bounded(instance: str) -> _InstanceCollection:
            async with semaphore:
                return await self._fetch_public_instance(
                    instance,
                    hashtag=hashtag,
                    page_limit=page_limit,
                    pages=pages,
                )

        return list(
            await asyncio.gather(*(bounded(instance) for instance in self.public_instances))
        )

    async def _fetch_public_instance(
        self,
        instance: str,
        *,
        hashtag: str | None,
        page_limit: int,
        pages: int,
    ) -> _InstanceCollection:
        path = (
            f"/api/v1/timelines/tag/{quote(hashtag, safe='')}"
            if hashtag
            else "/api/v1/timelines/public"
        )
        statuses: list[dict[str, Any]] = []
        fetched_count = 0
        malformed_count = 0
        params: dict[str, Any] = {"limit": min(40, page_limit)}
        try:
            for page_number in range(pages):
                payload, _ = await self.request_json(
                    "GET",
                    f"{instance}{path}",
                    params=params,
                    reset_diagnostics=page_number == 0,
                )
                if not isinstance(payload, list):
                    raise ConnectorError(
                        "mastodon", "invalid_payload", "Mastodon returned an invalid timeline"
                    )
                fetched_count += len(payload)
                malformed_count += sum(not isinstance(row, dict) for row in payload)
                page = [row for row in payload if isinstance(row, dict)]
                statuses.extend(page)
                if not page or len(payload) < params["limit"]:
                    break
                last_id = page[-1].get("id")
                if not last_id:
                    break
                params["max_id"] = str(last_id)
            return _InstanceCollection(
                instance,
                tuple(statuses),
                self.last_diagnostics,
                fetched_count,
                malformed_count,
            )
        except ConnectorError as error:
            if error.status_code in {401, 422}:
                error = ConnectorError(
                    "mastodon",
                    "auth_required",
                    "Mastodon instance requires authentication for public timeline access",
                    status_code=error.status_code,
                )
            return _InstanceCollection(
                instance,
                tuple(statuses),
                self.last_diagnostics,
                fetched_count,
                malformed_count,
                error,
            )

    def _aggregate_diagnostics(
        self,
        results: list[_InstanceCollection],
        *,
        started: float,
        mode: str,
    ) -> None:
        successful = [result for result in results if result.error is None]
        self.last_diagnostics = ConnectorDiagnostics(
            http_status=200
            if successful
            else next(
                (
                    result.error.status_code
                    for result in results
                    if result.error and result.error.status_code
                ),
                None,
            ),
            request_latency_ms=max(
                (result.diagnostics.request_latency_ms for result in results), default=0
            ),
            total_latency_ms=(perf_counter() - started) * 1000,
            attempt_count=sum(result.diagnostics.attempt_count for result in results),
            attempt_latencies_ms=[
                latency for result in results for latency in result.diagnostics.attempt_latencies_ms
            ],
            details={
                "mode": mode,
                "instances": list(self.public_instances),
                "instance_results": [
                    {
                        "instance": result.instance,
                        "state": (
                            "PUBLIC_TIMELINE_AVAILABLE"
                            if result.error is None
                            else "AUTH_REQUIRED"
                            if result.error.code == "auth_required"
                            else "UNAVAILABLE"
                        ),
                        "http_status": (
                            result.diagnostics.http_status
                            or (result.error.status_code if result.error else None)
                        ),
                        "fetched": result.fetched_count,
                        "latency_ms": round(result.diagnostics.total_latency_ms, 2),
                        "error_category": result.error.code if result.error else None,
                    }
                    for result in results
                ],
            },
        )

    @staticmethod
    def _matches_query(item: ConnectorItem, query: str, *, exact_phrase: bool) -> bool:
        normalized_query = normalize_text(query)
        combined = normalize_text(
            " ".join(
                (
                    item.title or "",
                    item.text,
                    " ".join(f"#{tag}" for tag in item.hashtags or ()),
                )
            )
        )
        if not normalized_query:
            return False
        if exact_phrase:
            return normalized_query in combined
        query_tokens = set(tokenize(normalized_query))
        return bool(query_tokens) and query_tokens.issubset(set(tokenize(combined)))

    @staticmethod
    def _deduplicate_federated(
        items: list[ConnectorItem],
    ) -> tuple[list[ConnectorItem], int]:
        by_url: dict[str, ConnectorItem] = {}
        duplicates = 0
        for item in items:
            key = item.canonical_url.rstrip("/")
            existing = by_url.get(key)
            if existing is None:
                by_url[key] = item
                continue
            duplicates += 1
            observed = tuple(
                dict.fromkeys(
                    (
                        *existing.raw_metadata.get("observed_instances", ()),
                        *item.raw_metadata.get("observed_instances", ()),
                    )
                )
            )
            by_url[key] = replace(
                existing,
                raw_metadata={**existing.raw_metadata, "observed_instances": observed},
            )
        return list(by_url.values()), duplicates

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        wrapper = payload
        original = payload.get("reblog") if isinstance(payload.get("reblog"), dict) else payload
        account = original.get("account") or {}
        text = plain_text(original.get("content"))
        hashtags = (
            tuple(tag.get("name") for tag in original.get("tags", []) if tag.get("name")) or None
        )
        mentions = (
            tuple(item.get("acct") for item in original.get("mentions", []) if item.get("acct"))
            or None
        )
        instance = str(payload.get("_mirsad_instance") or self.instance_url or "unknown")
        canonical_url = str(original.get("url") or original.get("uri") or "")
        original_id = str(original["id"])
        external_id = str(original.get("uri") or f"{instance}:{original_id}")
        mode = (
            str(payload.get("_mirsad_mode"))
            if payload.get("_mirsad_mode")
            else AUTHENTICATED_MODE
            if self.authenticated_configured
            else PUBLIC_MODE
        )
        acquisition_mode = (
            AcquisitionMode.DIRECT_API
            if mode == AUTHENTICATED_MODE
            else AcquisitionMode.PUBLIC_TIMELINE
        )
        return ConnectorItem(
            source="mastodon",
            external_id=external_id,
            canonical_url=canonical_url,
            author=account.get("display_name") or account.get("acct"),
            author_handle=account.get("acct"),
            author_verified=None,
            title=plain_text(original.get("spoiler_text")) or None,
            text=text,
            published_at=parse_datetime(original.get("created_at")),
            language=str(original.get("language") or "und"),
            hashtags=hashtags,
            mentions=mentions,
            media_type="post" if not original.get("media_attachments") else "post_media",
            raw_metrics=available_metrics(
                original,
                {
                    "likes": "favourites_count",
                    "reposts": "reblogs_count",
                    "replies": "replies_count",
                },
            ),
            raw_metadata={
                "source_type": "post",
                "collection_mode": mode,
                "acquisition_mode": acquisition_mode.value,
                "instance": instance,
                "observed_instances": (instance,),
                "content_html": original.get("content"),
                "wrapper_url": wrapper.get("url"),
                "wrapper_content_html": wrapper.get("content"),
                "visibility": original.get("visibility"),
                "reblog": wrapper.get("reblog"),
                "media_attachments": original.get("media_attachments"),
            },
            acquisition_mode=acquisition_mode,
        )
