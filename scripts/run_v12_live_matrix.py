from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

API_ROOT = "http://127.0.0.1:8000/api/v1"
OUTPUT = Path("reports/v1.2-live-matrix.json")
AUTOMATIC_COMPATIBILITY_SOURCES = [
    "bluesky",
    "hacker_news",
    "github",
    "gdelt",
    "rss",
]

CASES: tuple[dict[str, Any], ...] = (
    {"id": "baghdad", "query": "بغداد", "time_range": "7d"},
    {"id": "planning_ministry", "query": "وزارة التخطيط", "time_range": "all"},
    {"id": "arabic_ai", "query": "الذكاء الاصطناعي", "time_range": "7d"},
    {"id": "openai", "query": "OpenAI", "time_range": "30d"},
    {"id": "linux_security", "query": "Linux kernel security", "time_range": "30d"},
    {"id": "baghdad_hashtag", "query": "#بغداد", "time_range": "7d"},
    {"id": "openai_handle", "query": "@openai", "time_range": "30d"},
    {
        "id": "cve_identifier",
        "query": "CVE-2026-61371",
        "time_range": "all",
        "exact_phrase": True,
    },
    {"id": "historical_iraq", "query": "Iraq 2003 reconstruction", "time_range": "all"},
)


def connector_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        source = str(row.get("source"))
        current = summary.setdefault(
            source,
            {
                "requests": 0,
                "fetched": 0,
                "matched": 0,
                "admitted": 0,
                "final": 0,
                "latency_ms": 0.0,
                "statuses": [],
                "error_categories": [],
            },
        )
        current["requests"] += int(row.get("attempt_count") or 0)
        current["fetched"] += int(row.get("fetched_results") or 0)
        current["matched"] = max(
            current["matched"], int(row.get("final_matching_results") or 0)
        )
        current["admitted"] = max(
            current["admitted"], int(row.get("candidate_admitted_results") or 0)
        )
        current["final"] = max(
            current["final"], int(row.get("final_top_results") or 0)
        )
        current["latency_ms"] = round(
            current["latency_ms"] + float(row.get("latency_ms") or 0), 3
        )
        current["statuses"].append(row.get("status"))
        if row.get("error_category"):
            current["error_categories"].append(row["error_category"])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-fix-session")
    args = parser.parse_args()
    if args.post_fix_session:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            response = client.get(f"{API_ROOT}/searches/{args.post_fix_session}")
            response.raise_for_status()
            body = response.json()
            diagnostics_response = client.get(
                f"{API_ROOT}/searches/{args.post_fix_session}/diagnostics"
            )
            diagnostics_response.raise_for_status()
            diagnostics = diagnostics_response.json()["diagnostics"]
        report = json.loads(OUTPUT.read_text(encoding="utf-8"))
        report["post_fix_validation"] = {
            "reason": "Coverage now uses the planner current-health snapshot.",
            "session_id": args.post_fix_session,
            "status": body["session"]["status"],
            "results": body["session"]["result_count"],
            "coverage": body["coverage"],
            "connector_completion_order": diagnostics.get(
                "connector_completion_order", []
            ),
            "phase_timings_ms": diagnostics.get("phase_timings_ms", {}),
        }
        OUTPUT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"post_fix_session": args.post_fix_session}))
        return
    cases: list[dict[str, Any]] = []
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        sources = client.get(f"{API_ROOT}/sources")
        sources.raise_for_status()
        source_states = sources.json()
        for index, case in enumerate(CASES):
            if index:
                time.sleep(0.75)
            payload = {
                "query": case["query"],
                # Automatic planning uses the backend registry. This non-empty
                # compatibility field mirrors the browser's stable default.
                "sources": AUTOMATIC_COMPATIBILITY_SOURCES,
                "source_selection": "auto",
                "time_range": case["time_range"],
                "language": "all",
                "sort": "best_match",
                "search_mode": "balanced",
                "limit": 20,
                "exact_phrase": bool(case.get("exact_phrase", False)),
            }
            started_at = datetime.now(UTC)
            response = client.post(f"{API_ROOT}/searches", json=payload)
            completed_at = datetime.now(UTC)
            if response.status_code != 201:
                cases.append(
                    {
                        **case,
                        "http_status": response.status_code,
                        "error": response.text[:500],
                    }
                )
                continue
            body = response.json()
            session_id = body["session"]["id"]
            diagnostic_response = client.get(
                f"{API_ROOT}/searches/{session_id}/diagnostics"
            )
            diagnostic_response.raise_for_status()
            diagnostics = diagnostic_response.json()["diagnostics"]
            coverage_response = client.get(
                f"{API_ROOT}/searches/{session_id}/coverage"
            )
            coverage_response.raise_for_status()
            coverage = coverage_response.json()
            trace = diagnostics.get("mafer") or {}
            production = trace.get("resource_plan") or {}
            shadow = trace.get("shadow_router") or {}
            timings = diagnostics.get("phase_timings_ms") or {}
            cases.append(
                {
                    **case,
                    "session_id": session_id,
                    "http_status": response.status_code,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                    "wall_time_ms": round(
                        (completed_at - started_at).total_seconds() * 1000, 3
                    ),
                    "status": body["session"]["status"],
                    "intent": diagnostics.get("query", {}).get("intent"),
                    "production_plan": [
                        row.get("source") for row in production.get("resources", [])
                    ],
                    "production_rounds": production.get("rounds", []),
                    "adaptive_plan": shadow.get("recommended_sources", []),
                    "adaptive_deferred": shadow.get("deferred_sources", []),
                    "adaptive_mode": shadow.get("mode"),
                    "executed_sources": diagnostics.get(
                        "connector_completion_order", []
                    ),
                    "coverage": {
                        "status": coverage.get("coverage_status"),
                        "lanes": coverage.get("lanes", []),
                        "gaps": coverage.get("gaps", []),
                        "represented_platforms": coverage.get(
                            "represented_platforms", []
                        ),
                        "web_discovery": coverage.get("web_discovery"),
                    },
                    "per_source": connector_summary(
                        diagnostics.get("connectors", [])
                    ),
                    "acquisition_funnel": diagnostics.get(
                        "acquisition_funnel", []
                    ),
                    "planning_ms": timings.get("adaptive_planning"),
                    "local_retrieval_ms": timings.get("local_memory_retrieval"),
                    "live_collection_ms": timings.get("connector_collection"),
                    "historical_retrieval_ms": None,
                    "semantic_preparation_ms": timings.get("semantic_preparation"),
                    "ranking_ms": timings.get("ranking"),
                    "clustering_ms": timings.get("clustering"),
                    "total_ms": body["session"]["duration_ms"],
                    "results": body["session"]["result_count"],
                    "unique": body["session"]["unique_count"],
                    "clusters": len(body.get("clusters", [])),
                    "stop_reason": coverage.get("stop_reason"),
                    "stop_explanation": coverage.get("stop_explanation"),
                }
            )
    report = {
        "schema": "mirsad.v1.2.live-matrix",
        "captured_at": datetime.now(UTC).isoformat(),
        "observational_only": True,
        "external_network_variance": True,
        "production_router_changed": False,
        "source_states_before": source_states,
        "cases": cases,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "cases": len(cases)}))


if __name__ == "__main__":
    main()
