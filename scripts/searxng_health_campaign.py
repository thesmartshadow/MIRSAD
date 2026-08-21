from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from mirsad_api.discovery.searxng import DiscoveryProviderError, SearxngClient

ENGINES = ("brave", "duckduckgo", "qwant", "startpage")
OUTPUT = Path("reports/production-evidence/searxng-engine-health.json")


def _state(reason: str) -> str:
    lowered = reason.casefold()
    if "captcha" in lowered:
        return "CAPTCHA_BLOCKED"
    if "429" in lowered or "rate" in lowered or "too many" in lowered:
        return "RATE_LIMITED"
    if "timeout" in lowered:
        return "DEGRADED"
    return "UNAVAILABLE"


async def run() -> dict[str, object]:
    client = SearxngClient(
        "http://127.0.0.1:8080",
        timeout=5,
        engines=ENGINES,
    )
    try:
        response = await client.search("MIRSAD public information", max_engines=len(ENGINES))
        returned = Counter(
            engine
            for result in response.results
            for engine in result.engines
            if engine != "unknown"
        )
        unresponsive = dict(response.unresponsive_engines)
        engines = {
            engine: {
                "state": _state(unresponsive[engine])
                if engine in unresponsive
                else "HEALTHY"
                if returned[engine]
                else "DEGRADED",
                "returned_results": returned[engine],
                "reason": unresponsive.get(engine),
            }
            for engine in ENGINES
        }
        payload: dict[str, object] = {
            "schema": "mirsad.searxng-one-shot-engine-health",
            "generated_at": datetime.now(UTC).isoformat(),
            "requests": 1,
            "query": "MIRSAD public information",
            "http_status": response.http_status,
            "latency_ms": round(response.latency_ms, 2),
            "total_results": len(response.results),
            "engines": engines,
            "application_state": "LIVE"
            if response.results
            else "DEGRADED_EXTERNAL",
        }
    except DiscoveryProviderError as exc:
        payload = {
            "schema": "mirsad.searxng-one-shot-engine-health",
            "generated_at": datetime.now(UTC).isoformat(),
            "requests": 1,
            "query": "MIRSAD public information",
            "http_status": exc.status_code,
            "error": exc.code,
            "application_state": "DEGRADED_EXTERNAL",
            "engines": {},
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
