from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

from ..provenance import AcquisitionMode

CapabilityValue = bool | Literal["conditional"]


def exact_query_text(query: str, exact_phrase: bool) -> str:
    """Quote an exact query once while preserving the user's literal text."""

    text = query.strip()
    if not exact_phrase:
        return text
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        return text
    return f'"{text}"'


@dataclass(frozen=True, slots=True)
class ConnectorCapabilities:
    keyword_search: CapabilityValue = False
    phrase_search: CapabilityValue = False
    hashtag_search: CapabilityValue = False
    author_search: CapabilityValue = False
    recent_search: CapabilityValue = False
    historical_search: CapabilityValue = False
    language_filter: CapabilityValue = False
    date_filter: CapabilityValue = False
    public_posts: CapabilityValue = False
    comments: CapabilityValue = False
    engagement_metrics: CapabilityValue = False
    pagination: CapabilityValue = False
    requires_credentials: bool = False
    requires_approval: bool = False
    paid_access: CapabilityValue = False
    public_timeline: CapabilityValue = False
    hashtag_timeline: CapabilityValue = False
    authenticated_fulltext_search: CapabilityValue = False
    instance_scoped: CapabilityValue = False
    content_types: tuple[str, ...] = ()
    search_modes: tuple[str, ...] = ()
    sort_modes: tuple[str, ...] = ()
    acquisition_modes: tuple[str, ...] = ()
    web_index_search: CapabilityValue = False
    official_embed: CapabilityValue = False
    historical_index: CapabilityValue = False
    full_text_search: CapabilityValue = False
    identifier_search: CapabilityValue = False

    def as_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class ConnectorMetadata:
    key: str
    name: str
    kind: str
    base_url: str
    requires_credentials: bool = False
    confidence: float = 70.0
    category: Literal["social", "news", "developer_community"] = "developer_community"
    support_level: Literal["supported", "supported_with_credentials", "restricted_access"] = (
        "supported"
    )
    coverage_label: str | None = None
    capabilities: ConnectorCapabilities = field(default_factory=ConnectorCapabilities)
    allowed_base_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectorItem:
    source: str
    external_id: str
    canonical_url: str
    author: str | None
    title: str | None
    text: str
    published_at: datetime | None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    language: str = "und"
    author_handle: str | None = None
    author_verified: bool | None = None
    hashtags: tuple[str, ...] | None = None
    mentions: tuple[str, ...] | None = None
    media_type: str | None = None
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    acquisition_mode: AcquisitionMode = AcquisitionMode.DIRECT_API


@dataclass(frozen=True, slots=True)
class ConnectorSearchOptions:
    exact_phrase: bool = False
    language: str = "all"
    sort: str = "best_match"
    content_types: tuple[str, ...] = ()
    has_media: bool | None = None
    has_links: bool | None = None
    hashtags: tuple[str, ...] = ()
    source_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    original_query: str = ""
    query_variants: tuple[str, ...] = ()
    query_variant_metadata: tuple[dict[str, Any], ...] = ()
    query_intent: str = "keywords"
    time_range: str = "all"
    search_round: int = 1
    search_mode: str = "balanced"
    max_discovery_engine_calls: int = 0
    max_discovered_urls: int = 0
    max_historical_calls: int = -1

    def for_source(self, source: str) -> dict[str, Any]:
        value = self.source_options.get(source, {})
        return value if isinstance(value, dict) else {}


@dataclass(slots=True)
class ConnectorDiagnostics:
    http_status: int | None = None
    request_latency_ms: float = 0
    total_latency_ms: float = 0
    attempt_count: int = 0
    attempt_latencies_ms: list[float] = field(default_factory=list)
    raw_result_count: int = 0
    fetched_result_count: int = 0
    schema_valid_count: int = 0
    query_match_count: int = 0
    time_eligible_count: int = 0
    normalized_result_count: int = 0
    malformed_count: int = 0
    query_excluded_count: int = 0
    time_excluded_count: int = 0
    circuit_breaker_state: str = "closed"
    warning_code: str | None = None
    warning_message: str | None = None
    warning_status_code: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConnectorValidation:
    state: Literal["pass", "warn", "fail"]
    code: str
    message: str
    request_performed: bool = False


class ConnectorError(Exception):
    def __init__(
        self,
        source: str,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "status_code": self.status_code,
        }


class BaseConnector(ABC):
    metadata: ConnectorMetadata

    def __init__(
        self,
        *,
        timeout: float = 8.0,
        retries: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = max(0, min(retries, 2))
        self.transport = transport
        self._diagnostics: ContextVar[ConnectorDiagnostics | None] = ContextVar(
            f"{self.metadata.key}_connector_diagnostics", default=None
        )
        self.last_diagnostics = ConnectorDiagnostics()

    @property
    def last_diagnostics(self) -> ConnectorDiagnostics:
        diagnostics = self._diagnostics.get()
        if diagnostics is None:
            diagnostics = ConnectorDiagnostics()
            self._diagnostics.set(diagnostics)
        return diagnostics

    @last_diagnostics.setter
    def last_diagnostics(self, value: ConnectorDiagnostics) -> None:
        self._diagnostics.set(value)

    @abstractmethod
    def validate_configuration(self) -> tuple[bool, str | None]: ...

    @abstractmethod
    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]: ...

    @abstractmethod
    def normalize(self, payload: dict[str, Any]) -> ConnectorItem: ...

    def configuration_state(self) -> str:
        configured, _ = self.validate_configuration()
        if configured:
            return "configured"
        if self.metadata.support_level == "restricted_access":
            return "restricted"
        return "unconfigured"

    def active_acquisition_mode(self) -> str:
        modes = self.metadata.capabilities.acquisition_modes
        return modes[0] if modes else AcquisitionMode.DIRECT_API.value

    async def search_with_options(
        self,
        query: str,
        *,
        limit: int,
        since: datetime | None = None,
        options: ConnectorSearchOptions | None = None,
    ) -> list[ConnectorItem]:
        return await self.search(query, limit=limit, since=since)

    async def health_check(self) -> dict[str, Any]:
        configured, reason = self.validate_configuration()
        return {
            "status": "unknown" if configured else self.configuration_state(),
            "detail": reason or "Configured; no live request performed",
            "checked_at": datetime.now(UTC).isoformat(),
        }

    async def validate_access(self) -> ConnectorValidation:
        configured, reason = self.validate_configuration()
        if not configured:
            return ConnectorValidation(
                state="warn",
                code=self.configuration_state(),
                message=reason or "Source is not configured",
            )
        return ConnectorValidation(
            state="pass",
            code="configuration_valid",
            message="No credentials required; local configuration is valid",
        )

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: Any | None = None,
        content: str | bytes | None = None,
        reset_diagnostics: bool = True,
    ) -> tuple[Any, float]:
        allowed = (self.metadata.base_url, *self.metadata.allowed_base_urls)
        if not any(self._url_is_allowed(url, base) for base in allowed):
            raise ConnectorError(self.metadata.key, "invalid_host", "Connector host is not allowed")
        last_error: Exception | None = None
        request_started = perf_counter()
        if reset_diagnostics:
            self.last_diagnostics = ConnectorDiagnostics()
        previous_total = self.last_diagnostics.total_latency_ms
        for attempt in range(self.retries + 1):
            started = perf_counter()
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=False,
                    transport=self.transport,
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        headers=headers,
                        json=json_body,
                        content=content,
                    )
                latency = (perf_counter() - started) * 1000
                self.last_diagnostics.attempt_count += 1
                self.last_diagnostics.attempt_latencies_ms.append(round(latency, 2))
                self.last_diagnostics.http_status = response.status_code
                self.last_diagnostics.request_latency_ms = latency
                if response.is_error:
                    error = self._http_error(response)
                    if error.retryable and attempt < self.retries:
                        await asyncio.sleep(self._retry_delay(attempt, response))
                        continue
                    self.last_diagnostics.total_latency_ms = (
                        previous_total + (perf_counter() - request_started) * 1000
                    )
                    raise error
                try:
                    self.last_diagnostics.total_latency_ms = (
                        previous_total + (perf_counter() - request_started) * 1000
                    )
                    return response.json(), latency
                except ValueError as exc:
                    self.last_diagnostics.total_latency_ms = (
                        previous_total + (perf_counter() - request_started) * 1000
                    )
                    raise ConnectorError(
                        self.metadata.key,
                        "invalid_payload",
                        "Source returned an invalid response payload",
                        status_code=response.status_code,
                    ) from exc
            except ConnectorError:
                raise
            except asyncio.CancelledError:
                latency = (perf_counter() - started) * 1000
                self.last_diagnostics.attempt_count += 1
                self.last_diagnostics.attempt_latencies_ms.append(round(latency, 2))
                self.last_diagnostics.request_latency_ms = latency
                self.last_diagnostics.total_latency_ms = (
                    previous_total + (perf_counter() - request_started) * 1000
                )
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                latency = (perf_counter() - started) * 1000
                self.last_diagnostics.attempt_count += 1
                self.last_diagnostics.attempt_latencies_ms.append(round(latency, 2))
                self.last_diagnostics.request_latency_ms = latency
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(self._retry_delay(attempt))
        code = "timeout" if isinstance(last_error, httpx.TimeoutException) else "dns_network"
        message = (
            "Source request timed out" if code == "timeout" else "Source network request failed"
        )
        self.last_diagnostics.total_latency_ms = (
            previous_total + (perf_counter() - request_started) * 1000
        )
        raise ConnectorError(
            self.metadata.key,
            code,
            message,
            retryable=True,
        ) from last_error

    def normalize_payloads(self, payloads: list[dict[str, Any]]) -> list[ConnectorItem]:
        output: list[ConnectorItem] = []
        malformed = 0
        for payload in payloads:
            try:
                item = self.normalize(payload)
                if not self._valid_item(item):
                    malformed += 1
                    continue
                output.append(item)
            except (KeyError, TypeError, ValueError, OverflowError):
                malformed += 1
        self.last_diagnostics.raw_result_count = len(payloads)
        self.last_diagnostics.fetched_result_count = len(payloads)
        self.last_diagnostics.schema_valid_count = len(output)
        self.last_diagnostics.query_match_count = len(output)
        self.last_diagnostics.time_eligible_count = len(output)
        self.last_diagnostics.normalized_result_count = len(output)
        self.last_diagnostics.malformed_count = malformed
        return output

    @staticmethod
    def _valid_item(item: ConnectorItem) -> bool:
        if not item.external_id.strip() or not (item.title or item.text).strip():
            return False
        return item.canonical_url.startswith(("https://", "http://"))

    def _http_error(self, response: httpx.Response) -> ConnectorError:
        status = response.status_code
        categories = {
            401: ("http_401", "Source authentication was rejected", False),
            403: ("http_403", "Source access is unavailable from this environment", False),
            404: ("http_404", "Source endpoint was not found", False),
            429: ("rate_limited", "Source rate limit reached", True),
        }
        if status == 402:
            return ConnectorError(
                self.metadata.key,
                "quota_exhausted",
                "Source quota or paid access is exhausted",
                status_code=status,
            )
        if status in categories:
            code, message, retryable = categories[status]
        elif 500 <= status <= 599:
            code, message, retryable = (
                "upstream_5xx",
                "Source service is temporarily unavailable",
                True,
            )
        else:
            code, message, retryable = "http_error", f"Source returned HTTP {status}", False
        return ConnectorError(
            self.metadata.key,
            code,
            message,
            retryable=retryable,
            status_code=status,
        )

    @staticmethod
    def _retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                return min(2.0, max(0.1, float(retry_after)))
        return min(1.0, 0.25 * (2**attempt))

    @staticmethod
    def _url_is_allowed(url: str, base: str) -> bool:
        requested = urlsplit(url)
        allowed = urlsplit(base)
        if (requested.scheme, requested.netloc) != (allowed.scheme, allowed.netloc):
            return False
        base_path = allowed.path.rstrip("/")
        return (
            not base_path
            or requested.path == base_path
            or requested.path.startswith(f"{base_path}/")
        )


def parse_datetime(value: str | int | float | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None
