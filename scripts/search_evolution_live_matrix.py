#!/usr/bin/env python3
"""Run the bounded, non-destructive MIRSAD v1.1 live search matrix."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

QUERIES = (
    "بغداد",
    "الذكاء الاصطناعي",
    "وزارة التخطيط",
    "#بغداد",
    "Linux kernel security",
    "OpenAI",
    "CVE-2026-61371",
    "@openai",
)
TERMINAL_EVENTS = {"search.completed", "search.partial", "search.failed"}
SOURCE_TERMINAL_EVENTS = {
    "source.completed",
    "source.degraded",
    "source.failed",
}


def _milliseconds(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _source_totals(connectors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for entry in connectors:
        source = str(entry.get("source", "unknown"))
        current = totals.setdefault(
            source,
            {
                "requests": 0,
                "fetched": 0,
                "matched": 0,
                "normalized": 0,
                "admitted": 0,
                "final_top_k": 0,
                "latency_ms": 0.0,
                "statuses": [],
                "errors": [],
                "request_variants": [],
            },
        )
        current["requests"] += int(entry.get("attempt_count") or 0)
        current["fetched"] += int(entry.get("fetched_results") or 0)
        current["matched"] = max(
            current["matched"], int(entry.get("final_matching_results") or 0)
        )
        current["normalized"] += int(entry.get("normalized_results") or 0)
        current["admitted"] = max(
            current["admitted"], int(entry.get("candidate_admitted_results") or 0)
        )
        current["final_top_k"] = max(
            current["final_top_k"], int(entry.get("final_top_results") or 0)
        )
        current["latency_ms"] = round(
            current["latency_ms"] + float(entry.get("total_connector_latency_ms") or 0),
            2,
        )
        status = entry.get("status")
        if status and status not in current["statuses"]:
            current["statuses"].append(status)
        error = entry.get("error_category")
        if error and error not in current["errors"]:
            current["errors"].append(error)
        for variant in entry.get("query_variant_texts") or []:
            if variant not in current["request_variants"]:
                current["request_variants"].append(variant)
    return totals


async def _consume_events(
    client: httpx.AsyncClient,
    events_url: str,
    started: float,
) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
    events: list[dict[str, Any]] = []
    timings: dict[str, float | None] = {
        "first_event_ms": None,
        "first_source_completion_ms": None,
        "ranking_started_ms": None,
        "final_event_ms": None,
    }
    async with client.stream("GET", events_url, timeout=45.0) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            events.append(event)
            event_name = event["event"]
            elapsed = _milliseconds(started)
            if timings["first_event_ms"] is None:
                timings["first_event_ms"] = elapsed
            if (
                timings["first_source_completion_ms"] is None
                and event_name in SOURCE_TERMINAL_EVENTS
            ):
                timings["first_source_completion_ms"] = elapsed
            if event_name == "ranking.started" and timings["ranking_started_ms"] is None:
                timings["ranking_started_ms"] = elapsed
            if event_name in TERMINAL_EVENTS:
                timings["final_event_ms"] = elapsed
                break
    return events, timings


async def run_case(client: httpx.AsyncClient, query: str) -> dict[str, Any]:
    time_range = "all" if query == "CVE-2026-61371" else "30d"
    payload = {
        "query": query,
        "sources": ["bluesky", "hacker_news", "github", "gdelt", "rss"],
        "time_range": time_range,
        "language": "all",
        "limit": 30,
        "exact_phrase": query == "CVE-2026-61371",
        "sort": "best_match",
        "search_mode": "balanced",
        "source_selection": "auto",
    }
    started = time.perf_counter()
    response = await client.post("/search/jobs", json=payload, timeout=10.0)
    response.raise_for_status()
    job = response.json()
    job_created_ms = _milliseconds(started)
    events, client_timings = await _consume_events(
        client,
        f"/search/jobs/{job['job_id']}/events",
        started,
    )
    final = (await client.get(f"/searches/{job['session_id']}", timeout=15.0)).json()
    diagnostics = (
        await client.get(f"/searches/{job['session_id']}/diagnostics", timeout=15.0)
    ).json()["diagnostics"]
    mafer = diagnostics.get("mafer") or {}
    fingerprint = mafer.get("intent_fingerprint") or {}
    phase = diagnostics.get("phase_timings_ms") or {}
    ranking = diagnostics.get("ranking") or {}
    preparation = ranking.get("semantic_preparation") or {}
    outcome = diagnostics.get("outcome") or {}
    session = final["session"]
    return {
        "query": query,
        "session_id": job["session_id"],
        "job_id": job["job_id"],
        "time_range": time_range,
        "search_mode": "balanced",
        "source_selection": "auto",
        "exact_phrase": payload["exact_phrase"],
        "intent": fingerprint.get("labels") or [],
        "selected_sources": diagnostics.get("selected_sources") or [],
        "searched_sources": sorted(
            {
                str(entry.get("source"))
                for entry in diagnostics.get("connectors") or []
                if entry.get("source")
            }
        ),
        "not_selected_sources": [
            event.get("data", {}).get("source")
            for event in events
            if event.get("event") == "source.skipped"
            and event.get("data", {}).get("reason") == "not_selected"
        ],
        "unavailable_sources": [
            event.get("data", {}).get("source")
            for event in events
            if event.get("event") == "source.skipped"
            and event.get("data", {}).get("reason")
            in {"unavailable", "unconfigured", "restricted", "web_discovery_disabled"}
        ],
        "external_limit_sources": outcome.get("external_limit_sources") or [],
        "client_timings_ms": {
            "job_created": job_created_ms,
            **client_timings,
        },
        "server_timings_ms": {
            "planning": phase.get("adaptive_planning"),
            "collection": phase.get("connector_collection"),
            "persistence": phase.get("persistence"),
            "deduplication": phase.get("deduplication"),
            "semantic": phase.get("semantic_reranking"),
            "precompute_wall": preparation.get("precompute_wall_ms"),
            "overlap_window": preparation.get("overlap_window_ms"),
            "semantic_work_hidden": preparation.get("semantic_work_hidden_ms"),
            "semantic_critical_path": ranking.get("semantic_critical_path_ms"),
            "ranking_cache_hits": ranking.get("ranking_cache_hits"),
            "ranking_cache_misses": ranking.get("ranking_cache_misses"),
            "ranking": phase.get("ranking"),
            "clustering": phase.get("clustering"),
            "total": phase.get("total"),
        },
        "source_funnel": _source_totals(diagnostics.get("connectors") or []),
        "acquisition_funnel": diagnostics.get("acquisition_funnel") or [],
        "events": [
            {
                "sequence": event["sequence"],
                "event": event["event"],
                "elapsed_ms": event["elapsed_ms"],
                "data": event.get("data") or {},
            }
            for event in events
        ],
        "results": session["result_count"],
        "unique": session["unique_count"],
        "clusters": len(final.get("clusters") or []),
        "status": session["status"],
        "stop_reason": mafer.get("stop_reason"),
        "outcome_reason": session.get("outcome_reason"),
        "warnings": session.get("warnings") or [],
        "top_results": [
            {
                "rank": rank,
                "source": result["source"],
                "title": result["title"],
                "url": result["canonical_url"],
                "relevance": result["explanation"]["relevance"],
                "snippet": result.get("relevant_snippet"),
            }
            for rank, result in enumerate(final.get("results", [])[:5], start=1)
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument(
        "--output", default="reports/search-evolution-live-matrix.json"
    )
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="replace matching query cases in an existing output artifact",
    )
    arguments = parser.parse_args()
    output = Path(arguments.output)
    result: dict[str, Any] = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "live_public_data": True,
        "operator_database_reset": False,
        "base_url": arguments.base_url,
        "cases": [],
    }
    queries = tuple(arguments.queries or QUERIES)
    if arguments.merge and output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        result["cases"] = [
            case for case in previous.get("cases", []) if case.get("query") not in queries
        ]
    async with httpx.AsyncClient(base_url=arguments.base_url) as client:
        for query in queries:
            result["cases"].append(await run_case(client, query))
            output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    asyncio.run(main())
