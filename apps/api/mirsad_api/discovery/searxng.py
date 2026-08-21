from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from time import monotonic, perf_counter
from typing import Any
from urllib.parse import urlsplit

import httpx


class DiscoveryProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: Any, *, limit: int = 5000) -> str | None:
    if value is None:
        return None
    parser = _TextExtractor()
    try:
        parser.feed(str(value))
    except (ValueError, TypeError):
        return None
    normalized = " ".join(" ".join(parser.parts).split())
    return normalized[:limit] or None


def validate_searxng_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except (ValueError, UnicodeError) as exc:
        raise ValueError("SearXNG URL is invalid") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("SearXNG URL must use HTTP or HTTPS")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("SearXNG URL must not contain credentials, query, or fragment")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("SearXNG URL port is invalid")
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{path}"


@dataclass(frozen=True, slots=True)
class SearxResult:
    url: str
    title: str | None
    snippet: str | None
    engines: tuple[str, ...]
    published_at: str | None
    language: str | None


@dataclass(frozen=True, slots=True)
class SearxResponse:
    results: tuple[SearxResult, ...]
    unresponsive_engines: tuple[tuple[str, str], ...]
    latency_ms: float
    http_status: int
    skipped_engines: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True)
class EngineCircuitState:
    state: str = "HEALTHY"
    consecutive_failures: int = 0
    open_until: float = 0.0
    successes: int = 0
    failures: int = 0

    def as_dict(self, now: float) -> dict[str, Any]:
        return {
            "state": self.state
            if self.open_until > now
            else ("HEALTHY" if self.successes else self.state),
            "consecutive_failures": self.consecutive_failures,
            "cooldown_remaining_seconds": round(max(0.0, self.open_until - now), 3),
            "successes": self.successes,
            "failures": self.failures,
        }


class SearxngClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 4.0,
        engines: tuple[str, ...] = (),
        transport: httpx.AsyncBaseTransport | None = None,
        clock=monotonic,
    ) -> None:
        self.base_url = validate_searxng_url(base_url)
        self.timeout = max(0.5, min(timeout, 10.0))
        self.engines = tuple(dict.fromkeys(engine.strip() for engine in engines if engine.strip()))
        self.transport = transport
        self._clock = clock
        self._circuits: dict[str, EngineCircuitState] = {
            engine: EngineCircuitState() for engine in self.engines
        }

    async def search(
        self,
        query: str,
        *,
        language: str = "all",
        time_range: str | None = None,
        max_engines: int = 0,
        preferred_engines: tuple[str, ...] = (),
    ) -> SearxResponse:
        now = self._clock()
        active_engines: list[str] = []
        skipped: list[tuple[str, str]] = []
        for engine in self.engines:
            circuit = self._circuits.setdefault(engine, EngineCircuitState())
            if circuit.open_until > now:
                skipped.append((engine, circuit.state))
            else:
                active_engines.append(engine)
        if preferred_engines:
            priority = {engine: index for index, engine in enumerate(preferred_engines)}
            active_engines.sort(key=lambda engine: (priority.get(engine, len(priority)), engine))
        if max_engines > 0:
            active_engines = active_engines[:max_engines]
        if self.engines and not active_engines:
            raise DiscoveryProviderError(
                "engines_temporarily_unavailable",
                "All configured SearXNG engines are in a temporary cooldown",
                retryable=True,
            )
        params: dict[str, str | int] = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": language if language in {"ar", "en"} else "all",
            "safesearch": 1,
            "pageno": 1,
        }
        if active_engines:
            params["engines"] = ",".join(active_engines)
        if time_range in {"day", "month", "year"}:
            params["time_range"] = time_range
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,
                transport=self.transport,
                headers={"Accept": "application/json", "User-Agent": "MIRSAD/1.0"},
            ) as client:
                response = await client.get(f"{self.base_url}/search", params=params)
        except httpx.TimeoutException as exc:
            raise DiscoveryProviderError(
                "timeout", "SearXNG search timed out", retryable=True
            ) from exc
        except httpx.NetworkError as exc:
            raise DiscoveryProviderError(
                "dns_network", "SearXNG search network request failed", retryable=True
            ) from exc
        latency = (perf_counter() - started) * 1000
        if response.status_code == 429:
            raise DiscoveryProviderError(
                "rate_limited", "SearXNG rate limit reached", status_code=429
            )
        if response.status_code == 403:
            raise DiscoveryProviderError(
                "http_403",
                "SearXNG JSON API is unavailable; enable the json search format",
                status_code=403,
            )
        if response.status_code >= 500:
            raise DiscoveryProviderError(
                "upstream_5xx",
                "SearXNG is temporarily unavailable",
                status_code=response.status_code,
                retryable=True,
            )
        if response.status_code != 200:
            raise DiscoveryProviderError(
                "http_error",
                f"SearXNG returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DiscoveryProviderError(
                "invalid_payload", "SearXNG returned invalid JSON"
            ) from exc
        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise DiscoveryProviderError(
                "invalid_payload", "SearXNG returned an invalid results payload"
            )
        parsed: list[SearxResult] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("url"), str):
                continue
            engines = row.get("engines")
            if not isinstance(engines, list):
                engines = [row.get("engine")] if row.get("engine") else []
            parsed.append(
                SearxResult(
                    url=row["url"],
                    title=plain_text(row.get("title"), limit=1000),
                    snippet=plain_text(row.get("content"), limit=5000),
                    engines=tuple(
                        sorted({str(engine) for engine in engines if isinstance(engine, str)})
                    )
                    or ("unknown",),
                    published_at=(
                        str(row.get("publishedDate")) if row.get("publishedDate") else None
                    ),
                    language=str(row.get("language")) if row.get("language") else None,
                )
            )
        unresponsive: list[tuple[str, str]] = []
        raw_unresponsive = payload.get("unresponsive_engines", [])
        if isinstance(raw_unresponsive, list):
            for value in raw_unresponsive:
                if isinstance(value, (list, tuple)) and value:
                    unresponsive.append(
                        (str(value[0]), str(value[1]) if len(value) > 1 else "unavailable")
                    )
                elif isinstance(value, str):
                    unresponsive.append((value, "unavailable"))
        self._update_circuits(parsed, unresponsive)
        return SearxResponse(
            tuple(parsed),
            tuple(unresponsive),
            latency,
            response.status_code,
            tuple(skipped),
        )

    def engine_states(self) -> dict[str, dict[str, Any]]:
        now = self._clock()
        return {engine: state.as_dict(now) for engine, state in sorted(self._circuits.items())}

    def _update_circuits(
        self,
        results: list[SearxResult],
        unresponsive: list[tuple[str, str]],
    ) -> None:
        now = self._clock()
        failed = {engine for engine, _reason in unresponsive}
        succeeded = {
            engine for result in results for engine in result.engines if engine not in failed
        }
        for engine in succeeded:
            state = self._circuits.setdefault(engine, EngineCircuitState())
            state.state = "HEALTHY"
            state.consecutive_failures = 0
            state.open_until = 0.0
            state.successes += 1
        for engine, reason in unresponsive:
            state = self._circuits.setdefault(engine, EngineCircuitState())
            state.consecutive_failures += 1
            state.failures += 1
            lowered = reason.casefold()
            if "captcha" in lowered:
                state.state = "CAPTCHA_BLOCKED"
                cooldown = 300.0
                threshold = 2
            elif "429" in lowered or "rate" in lowered or "too many requests" in lowered:
                state.state = "RATE_LIMITED"
                cooldown = 60.0
                threshold = 2
            elif "timeout" in lowered:
                state.state = "DEGRADED"
                cooldown = 15.0
                threshold = 2
            else:
                state.state = "TEMPORARILY_UNAVAILABLE"
                cooldown = 30.0
                threshold = 2
            if state.consecutive_failures >= threshold:
                state.open_until = now + cooldown

    async def health_check(self) -> tuple[bool, str, float]:
        started = perf_counter()
        try:
            response = await self.search("MIRSAD", language="en")
        except DiscoveryProviderError as exc:
            return False, exc.code, (perf_counter() - started) * 1000
        if not response.results and response.unresponsive_engines:
            return False, "upstream_engines_unavailable", response.latency_ms
        return True, "json_search_available", response.latency_ms
