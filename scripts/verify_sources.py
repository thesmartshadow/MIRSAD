from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from mirsad_api.config import Settings
from mirsad_api.connectors import BaseConnector, ConnectorError
from mirsad_api.services.registry import build_connector_registry

AUTH_FAILURES = {"http_401", "invalid_credentials"}
NETWORK_FAILURES = {"timeout", "dns_network", "upstream_5xx", "http_404"}


async def verify_one(connector: BaseConnector, *, timeout_seconds: float = 10.0) -> dict[str, Any]:
    started = perf_counter()
    configured, configuration_detail = connector.validate_configuration()
    try:
        validation = await asyncio.wait_for(
            connector.validate_access(), timeout=timeout_seconds
        )
        result: dict[str, Any] = {
            **asdict(validation),
            "internal_failure": False,
        }
    except TimeoutError:
        result = {
            "state": "fail",
            "code": "timeout",
            "message": "Credential validation exceeded the safe time budget",
            "request_performed": configured,
            "internal_failure": False,
        }
    except ConnectorError as exc:
        if exc.code in AUTH_FAILURES:
            message = "Authentication rejected"
        elif exc.code == "http_403":
            message = (
                "Configured access was forbidden by the source"
                if connector.metadata.requires_credentials
                else "Public endpoint access was forbidden from this environment"
            )
        elif exc.code == "access_limited":
            message = "Configured access does not permit this operation"
        elif exc.code == "quota_exhausted":
            message = "Configured quota or paid allowance is exhausted"
        elif exc.code == "rate_limited":
            message = "Validation request was rate limited"
        elif exc.code in NETWORK_FAILURES:
            message = exc.message
        else:
            message = exc.message
        result = {
            "state": "warn" if exc.code in {"rate_limited", "quota_exhausted"} else "fail",
            "code": exc.code,
            "message": message,
            "request_performed": True,
            "internal_failure": False,
        }
    except Exception:
        result = {
            "state": "fail",
            "code": "local_validation_error",
            "message": "Connector validation failed inside MIRSAD",
            "request_performed": False,
            "internal_failure": True,
        }
    diagnostics = connector.last_diagnostics
    return {
        "source": connector.metadata.key,
        "name": connector.metadata.name,
        "configuration_state": connector.configuration_state(),
        "configured": configured,
        "configuration_detail": configuration_detail,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "http_status": diagnostics.http_status,
        "attempt_count": diagnostics.attempt_count,
        **result,
    }


async def verify_all(settings: Settings | None = None) -> dict[str, Any]:
    registry = build_connector_registry(settings or Settings())
    results = await asyncio.gather(*(verify_one(connector) for connector in registry.values()))
    return {
        "schema": "mirsad.source-access-verification",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": results,
    }


def render(payload: dict[str, Any]) -> str:
    blocks = []
    for source in payload["sources"]:
        state = str(source["state"]).upper()
        blocks.append(
            "\n".join(
                [
                    source["name"],
                    state,
                    str(source["message"]),
                    f"latency {source['latency_ms']:.0f} ms",
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def main() -> None:
    try:
        payload = asyncio.run(verify_all())
    except Exception:
        print("MIRSAD source registry\nFAIL\nunable to initialize connector registry")
        raise SystemExit(2) from None
    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    (report_dir / "source-verification.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(render(payload), end="")
    if any(source["internal_failure"] for source in payload["sources"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
