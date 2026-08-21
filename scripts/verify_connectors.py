from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from mirsad_api.config import Settings
from mirsad_api.connectors import BaseConnector, ConnectorError
from mirsad_api.services.registry import build_connector_registry

DEFAULT_QUERIES = ("climate policy", "open data", "العراق")


def failure_state(code: str) -> str:
    if code in {"unconfigured", "configuration_missing"}:
        return "unconfigured"
    if code in {"restricted_access", "capability_restricted"}:
        return "restricted"
    if code == "access_limited":
        return "access_limited"
    if code == "quota_exhausted":
        return "quota_exhausted"
    if code == "rate_limited":
        return "rate_limited"
    if code in {"http_401", "http_403", "http_404", "dns_network"}:
        return "unavailable"
    return "degraded"


async def verify_connector(connector: BaseConnector, queries: tuple[str, ...]) -> dict[str, Any]:
    configured, detail = connector.validate_configuration()
    report: dict[str, Any] = {
        "source": connector.metadata.key,
        "name": connector.metadata.name,
        "configuration_state": connector.configuration_state(),
        "configuration_detail": detail,
        "category": connector.metadata.category,
        "support_level": connector.metadata.support_level,
        "coverage_label": connector.metadata.coverage_label,
        "capabilities": connector.metadata.capabilities.as_dict(),
        "timeout_seconds": connector.timeout,
        "retry_limit": connector.retries,
        "probes": [],
    }
    if not configured:
        report["state"] = connector.configuration_state()
        return report
    states: list[str] = []
    for query in queries:
        started = perf_counter()
        probe: dict[str, Any] = {"query": query}
        try:
            items = await connector.search(
                query, limit=10, since=datetime.now(UTC) - timedelta(days=7)
            )
            diagnostic = connector.last_diagnostics
            warning_code = diagnostic.warning_code
            malformed = diagnostic.malformed_count
            fetched = (
                diagnostic.fetched_result_count
                or diagnostic.raw_result_count
                or len(items)
            )
            probe.update(
                {
                    "state": "degraded" if warning_code or malformed else "healthy",
                    "http_status": diagnostic.http_status,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "raw_fetched_record_count": fetched,
                    "schema_valid_record_count": diagnostic.schema_valid_count or len(items),
                    "query_matching_record_count": diagnostic.query_match_count or len(items),
                    "time_eligible_record_count": diagnostic.time_eligible_count or len(items),
                    "returned_result_count": len(items),
                    "normalized_result_count": len(items),
                    "final_matching_result_count": len(items),
                    "malformed_records": malformed,
                    "query_excluded_records": diagnostic.query_excluded_count,
                    "time_excluded_records": diagnostic.time_excluded_count,
                    "attempt_count": diagnostic.attempt_count,
                    "attempt_latencies_ms": diagnostic.attempt_latencies_ms,
                    "total_connector_latency_ms": round(
                        diagnostic.total_latency_ms
                        or (perf_counter() - started) * 1000,
                        2,
                    ),
                    "circuit_breaker_state": diagnostic.circuit_breaker_state,
                    "error_category": warning_code or ("invalid_payload" if malformed else None),
                    "error": diagnostic.warning_message
                    or ("One or more records were malformed" if malformed else None),
                }
            )
        except ConnectorError as exc:
            diagnostic = connector.last_diagnostics
            probe.update(
                {
                    "state": failure_state(exc.code),
                    "http_status": exc.status_code or diagnostic.http_status,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "raw_fetched_record_count": diagnostic.fetched_result_count
                    or diagnostic.raw_result_count,
                    "schema_valid_record_count": diagnostic.schema_valid_count,
                    "query_matching_record_count": diagnostic.query_match_count,
                    "time_eligible_record_count": diagnostic.time_eligible_count,
                    "returned_result_count": 0,
                    "normalized_result_count": diagnostic.normalized_result_count,
                    "final_matching_result_count": diagnostic.normalized_result_count,
                    "malformed_records": diagnostic.malformed_count,
                    "query_excluded_records": diagnostic.query_excluded_count,
                    "time_excluded_records": diagnostic.time_excluded_count,
                    "attempt_count": diagnostic.attempt_count,
                    "attempt_latencies_ms": diagnostic.attempt_latencies_ms,
                    "total_connector_latency_ms": round(
                        diagnostic.total_latency_ms
                        or (perf_counter() - started) * 1000,
                        2,
                    ),
                    "circuit_breaker_state": diagnostic.circuit_breaker_state,
                    "error_category": exc.code,
                    "error": exc.message,
                }
            )
        except Exception:
            probe.update(
                {
                    "state": "degraded",
                    "http_status": connector.last_diagnostics.http_status,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "returned_result_count": 0,
                    "raw_fetched_record_count": 0,
                    "schema_valid_record_count": 0,
                    "query_matching_record_count": 0,
                    "time_eligible_record_count": 0,
                    "normalized_result_count": 0,
                    "final_matching_result_count": 0,
                    "malformed_records": 0,
                    "attempt_count": connector.last_diagnostics.attempt_count,
                    "attempt_latencies_ms": connector.last_diagnostics.attempt_latencies_ms,
                    "total_connector_latency_ms": round(
                        connector.last_diagnostics.total_latency_ms
                        or (perf_counter() - started) * 1000,
                        2,
                    ),
                    "circuit_breaker_state": connector.last_diagnostics.circuit_breaker_state,
                    "error_category": "connector_error",
                    "error": "Connector could not complete",
                }
            )
        report["probes"].append(probe)
        states.append(str(probe["state"]))
    report["state"] = (
        "healthy"
        if "healthy" in states
        else "rate_limited"
        if "rate_limited" in states
        else states[-1]
    )
    return report


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Live Connector Verification",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "| Connector | State | Probes | Fetched | Matched | Normalized | Latency | Limitation |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for connector in payload["connectors"]:
        probes = connector["probes"]
        fetched = sum(probe.get("raw_fetched_record_count", 0) for probe in probes)
        matched = sum(probe.get("query_matching_record_count", 0) for probe in probes)
        records = sum(probe.get("normalized_result_count", 0) for probe in probes)
        latency = sum(probe.get("latency_ms", 0) for probe in probes)
        errors = sorted(
            {probe.get("error_category") for probe in probes if probe.get("error_category")}
        )
        limitation = ", ".join(errors) or connector.get("configuration_detail") or "None observed"
        lines.append(
            f"| {connector['name']} | {connector['state']} | {len(probes)} | "
            f"{fetched} | {matched} | {records} | {latency:.0f} ms | {limitation} |"
        )
    lines.extend(
        [
            "",
            "This report reflects one environment and time. Live verification is supplemental and "
            "is not a CI dependency.",
        ]
    )
    return "\n".join(lines) + "\n"


async def run(queries: tuple[str, ...]) -> dict[str, Any]:
    connectors = build_connector_registry(Settings())
    reports = await asyncio.gather(
        *(verify_connector(connector, queries) for connector in connectors.values())
    )
    return {
        "schema": "mirsad.live-connector-verification",
        "version": "1.2",
        "generated_at": datetime.now(UTC).isoformat(),
        "queries": list(queries),
        "connectors": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify configured MIRSAD connectors")
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--output", default="reports")
    args = parser.parse_args()
    payload = asyncio.run(run(tuple(args.queries or DEFAULT_QUERIES)))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "live-connectors.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = markdown_report(payload)
    (output / "live-connectors.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
