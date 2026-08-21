from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic, perf_counter
from typing import Any

from ..provenance import AcquisitionMode
from .base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    parse_datetime,
)


class GdeltConnector(BaseConnector):
    metadata = ConnectorMetadata(
        key="gdelt",
        name="GDELT News",
        kind="news",
        base_url="https://api.gdeltproject.org",
        confidence=70,
        category="news",
        coverage_label="News indexed by GDELT DOC 2.0",
        capabilities=ConnectorCapabilities(
            keyword_search=True,
            phrase_search=True,
            recent_search=True,
            historical_search=True,
            language_filter=True,
            date_filter=True,
            full_text_search=True,
            identifier_search="conditional",
            content_types=("news",),
            acquisition_modes=("PUBLIC_API",),
        ),
    )

    def __init__(
        self,
        *,
        total_budget_seconds: float = 3.0,
        circuit_failure_threshold: int = 2,
        circuit_cooldown_seconds: float = 60.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.total_budget_seconds = max(0.25, total_budget_seconds)
        self.circuit_failure_threshold = max(1, circuit_failure_threshold)
        self.circuit_cooldown_seconds = max(1.0, circuit_cooldown_seconds)
        self._consecutive_budget_failures = 0
        self._circuit_open_until = 0.0

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        now_monotonic = monotonic()
        if self._circuit_open_until > now_monotonic:
            self.last_diagnostics = ConnectorDiagnostics(circuit_breaker_state="open")
            raise ConnectorError(
                self.metadata.key,
                "circuit_open",
                "GDELT is temporarily degraded after repeated timeouts",
                retryable=True,
            )
        circuit_state = "half_open" if self._circuit_open_until else "closed"
        now = datetime.now(UTC)
        age_hours = max(1, int((now - since).total_seconds() / 3600)) if since else 24 * 30
        timespan = f"{age_hours}h" if age_hours <= 24 else f"{min(30, max(1, age_hours // 24))}d"
        params: dict[str, Any] = {
            "query": query,
            "mode": "artlist",
            "maxrecords": min(limit, 25),
            "format": "json",
            "sort": "DateDesc",
            "timespan": timespan,
        }
        started = perf_counter()
        try:
            async with asyncio.timeout(self.total_budget_seconds):
                payload, _latency = await self.request_json(
                    "GET", f"{self.metadata.base_url}/api/v2/doc/doc", params=params
                )
        except TimeoutError as exc:
            self._record_budget_failure()
            self.last_diagnostics.total_latency_ms = (perf_counter() - started) * 1000
            self.last_diagnostics.circuit_breaker_state = self.circuit_breaker_state
            raise ConnectorError(
                self.metadata.key,
                "timeout",
                "GDELT exceeded the interactive search latency budget",
                retryable=True,
            ) from exc
        except ConnectorError as exc:
            if exc.code in {"timeout", "dns_network", "upstream_5xx"}:
                self._record_budget_failure()
            else:
                self._consecutive_budget_failures = 0
                self._circuit_open_until = 0.0
            self.last_diagnostics.total_latency_ms = (perf_counter() - started) * 1000
            self.last_diagnostics.circuit_breaker_state = self.circuit_breaker_state
            raise
        self._consecutive_budget_failures = 0
        self._circuit_open_until = 0.0
        self.last_diagnostics.total_latency_ms = (perf_counter() - started) * 1000
        self.last_diagnostics.circuit_breaker_state = (
            "closed" if circuit_state in {"closed", "half_open"} else circuit_state
        )
        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise ConnectorError(
                self.metadata.key,
                "invalid_payload",
                "GDELT returned an invalid article list",
                status_code=self.last_diagnostics.http_status,
            )
        return self.normalize_payloads(articles)

    @property
    def circuit_breaker_state(self) -> str:
        return "open" if self._circuit_open_until > monotonic() else "closed"

    def _record_budget_failure(self) -> None:
        self._consecutive_budget_failures += 1
        if self._consecutive_budget_failures >= self.circuit_failure_threshold:
            self._circuit_open_until = monotonic() + self.circuit_cooldown_seconds

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        url = str(payload.get("url", ""))
        date = payload.get("seendate")
        if isinstance(date, str) and len(date) == 15 and date.endswith("Z"):
            try:
                published = datetime.strptime(date, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            except ValueError:
                published = None
        else:
            published = parse_datetime(date)
        return ConnectorItem(
            source=self.metadata.key,
            external_id=url or str(payload.get("title", "unknown")),
            canonical_url=url,
            author=payload.get("domain"),
            title=payload.get("title"),
            text=str(payload.get("title") or ""),
            published_at=published,
            language=str(payload.get("language") or "und").lower()[:10],
            # GDELT DOC results do not expose a comparable public engagement count.
            raw_metrics={},
            raw_metadata={
                "source_type": "article",
                "domain": payload.get("domain"),
                "source_country": payload.get("sourcecountry"),
                "image_url": payload.get("socialimage"),
            },
            acquisition_mode=AcquisitionMode.PUBLIC_API,
        )
