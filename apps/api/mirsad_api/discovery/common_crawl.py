from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from .classifiers import classify_platform_url
from .searxng import DiscoveryProviderError


@dataclass(frozen=True, slots=True)
class HistoricalCapture:
    canonical_url: str
    timestamp: str | None
    status: str | None
    mime: str | None
    digest: str | None


@dataclass(frozen=True, slots=True)
class HistoricalLookup:
    captures: tuple[HistoricalCapture, ...]
    collection: str
    latency_ms: float


class CommonCrawlAdapter:
    """Bounded capture metadata lookup for one already validated public URL."""

    def __init__(
        self,
        base_url: str = "https://index.commoncrawl.org",
        *,
        timeout: float = 3.0,
        max_captures: int = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parts = urlsplit(base_url.strip())
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("Common Crawl index URL must be a backend-configured HTTPS origin")
        self.base_url = f"https://{parts.netloc}{parts.path.rstrip('/')}"
        self.timeout = max(0.5, min(timeout, 8.0))
        self.max_captures = max(1, min(max_captures, 25))
        self.transport = transport
        self._collection: str | None = None

    async def lookup(self, platform: str, public_url: str) -> HistoricalLookup:
        classified = classify_platform_url(platform, public_url)
        if classified is None or not classified.is_content:
            raise DiscoveryProviderError(
                "invalid_historical_target",
                "Historical lookup requires a validated public post or comment URL",
            )
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,
                transport=self.transport,
                headers={"User-Agent": "MIRSAD/1.0 historical URL lookup"},
            ) as client:
                collection = await self._latest_collection(client)
                response = await client.get(
                    f"{self.base_url}/{collection}-index",
                    params={
                        "url": classified.canonical_url,
                        "output": "json",
                        "fl": "url,timestamp,status,mime,digest",
                        "filter": "status:200",
                        "collapse": "digest",
                    },
                    headers={"Accept": "application/x-ndjson"},
                )
        except httpx.TimeoutException as exc:
            raise DiscoveryProviderError(
                "timeout", "Common Crawl index lookup timed out", retryable=True
            ) from exc
        except httpx.NetworkError as exc:
            raise DiscoveryProviderError(
                "dns_network", "Common Crawl index network request failed", retryable=True
            ) from exc
        if response.status_code == 404:
            return HistoricalLookup((), collection, (perf_counter() - started) * 1000)
        if response.status_code == 429:
            raise DiscoveryProviderError(
                "rate_limited", "Common Crawl index rate limit reached", status_code=429
            )
        if response.status_code != 200:
            raise DiscoveryProviderError(
                "http_error",
                f"Common Crawl index returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        captures: list[HistoricalCapture] = []
        for line in response.text.splitlines()[: self.max_captures]:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(row, dict):
                continue
            candidate = classify_platform_url(platform, str(row.get("url") or ""))
            if candidate is None or candidate.canonical_url != classified.canonical_url:
                continue
            timestamp = str(row.get("timestamp")) if row.get("timestamp") else None
            if timestamp and len(timestamp) == 14:
                timestamp = (
                    f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]}T"
                    f"{timestamp[8:10]}:{timestamp[10:12]}:{timestamp[12:14]}Z"
                )
            if timestamp:
                from ..connectors.base import parse_datetime

                parse_datetime(timestamp)
            captures.append(
                HistoricalCapture(
                    candidate.canonical_url,
                    timestamp,
                    str(row.get("status")) if row.get("status") else None,
                    str(row.get("mime")) if row.get("mime") else None,
                    str(row.get("digest")) if row.get("digest") else None,
                )
            )
        return HistoricalLookup(tuple(captures), collection, (perf_counter() - started) * 1000)

    async def _latest_collection(self, client: httpx.AsyncClient) -> str:
        if self._collection:
            return self._collection
        response = await client.get(f"{self.base_url}/collinfo.json")
        if response.status_code != 200:
            raise DiscoveryProviderError(
                "http_error",
                f"Common Crawl collection index returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            rows = response.json()
        except ValueError as exc:
            raise DiscoveryProviderError(
                "invalid_payload", "Common Crawl returned invalid collection metadata"
            ) from exc
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise DiscoveryProviderError(
                "invalid_payload", "Common Crawl returned no collection metadata"
            )
        collection = rows[0].get("id")
        if not isinstance(collection, str) or not collection.startswith("CC-MAIN-"):
            raise DiscoveryProviderError(
                "invalid_payload", "Common Crawl collection identifier is invalid"
            )
        self._collection = collection
        return collection
