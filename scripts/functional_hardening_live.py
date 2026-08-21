from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

API_ROOT = "http://127.0.0.1:8000/api/v1"
OUTPUT = Path("reports/functional-hardening-live-matrix.json")

CASES: tuple[dict[str, Any], ...] = (
    {"id": "baghdad", "query": "بغداد", "time_range": "7d"},
    {"id": "planning_ministry", "query": "وزارة التخطيط", "time_range": "7d"},
    {"id": "abwab", "query": "منصة ابواب", "time_range": "7d"},
    {"id": "arabic_ai", "query": "الذكاء الاصطناعي", "time_range": "7d"},
    {"id": "microsoft_iraq", "query": "Microsoft العراق", "time_range": "7d"},
    {"id": "cve_recent", "query": "CVE-2026-61371", "time_range": "7d"},
    {
        "id": "cve_exact_all",
        "query": "CVE-2026-61371",
        "time_range": "all",
        "exact_phrase": True,
    },
    {"id": "handle_plain", "query": "thesmartshadow", "time_range": "7d"},
    {"id": "handle_at", "query": "@thesmartshadow", "time_range": "7d"},
    {"id": "hashtag_baghdad", "query": "#بغداد", "time_range": "7d"},
    {"id": "arabic_person", "query": "علي فراس", "time_range": "all"},
    {
        "id": "arabic_person_full",
        "query": "علي فراس محمد رضا",
        "time_range": "all",
    },
    {
        "id": "arabic_diacritized_exact",
        "query": "وِزَارَةُ التَّخْطِيط",
        "time_range": "all",
        "exact_phrase": True,
    },
)


def aggregate_connectors(connectors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in connectors:
        source = str(item["source"])
        aggregate = output.setdefault(
            source,
            {
                "requests": 0,
                "fetched": 0,
                "valid": 0,
                "matched": 0,
                "admitted": 0,
                "persisted": 0,
                "final_top": 0,
                "latency_ms": 0.0,
                "statuses": [],
                "errors": [],
                "query_variant_attempts": [],
                "query_variant_texts": [],
            },
        )
        aggregate["requests"] += int(item.get("attempt_count") or 0)
        aggregate["fetched"] += int(item.get("fetched_results") or 0)
        aggregate["valid"] += int(item.get("schema_valid_results") or 0)
        aggregate["matched"] = max(
            aggregate["matched"], int(item.get("final_matching_results") or 0)
        )
        aggregate["admitted"] = max(
            aggregate["admitted"], int(item.get("candidate_admitted_results") or 0)
        )
        aggregate["persisted"] = max(
            aggregate["persisted"], int(item.get("collected_results") or 0)
        )
        aggregate["final_top"] = max(
            aggregate["final_top"], int(item.get("final_top_results") or 0)
        )
        aggregate["latency_ms"] = round(
            aggregate["latency_ms"] + float(item.get("latency_ms") or 0), 2
        )
        aggregate["statuses"].append(item.get("status"))
        if item.get("error_category"):
            aggregate["errors"].append(item["error_category"])
        aggregate["query_variant_attempts"].extend(
            item.get("query_variant_attempts") or []
        )
        aggregate["query_variant_texts"].extend(item.get("query_variant_texts") or [])
    return output


def main() -> None:
    captured: list[dict[str, Any]] = []
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        source_response = client.get(f"{API_ROOT}/sources")
        source_response.raise_for_status()
        source_states = source_response.json()
        selectable_sources = [
            source["key"]
            for source in source_states
            if source["configured"]
            and source["enabled"]
            and source["configuration_state"] == "configured"
            and source["status"]
            not in {
                "disabled",
                "external_limit",
                "rate_limited",
                "restricted",
                "unavailable",
            }
        ]
        for case in CASES:
            payload = {
                "query": case["query"],
                "sources": selectable_sources,
                "source_selection": "auto",
                "time_range": case["time_range"],
                "language": "all",
                "sort": "best_match",
                "search_mode": "balanced",
                "limit": 30,
                "exact_phrase": bool(case.get("exact_phrase", False)),
            }
            started = datetime.now(UTC)
            response = client.post(f"{API_ROOT}/searches", json=payload)
            completed = datetime.now(UTC)
            if response.status_code != 201:
                captured.append(
                    {
                        **case,
                        "payload": payload,
                        "http_status": response.status_code,
                        "error": response.text[:1000],
                    }
                )
                continue
            body = response.json()
            session_id = body["session"]["id"]
            diagnostics_response = client.get(f"{API_ROOT}/searches/{session_id}/diagnostics")
            diagnostics_response.raise_for_status()
            diagnostics = diagnostics_response.json()["diagnostics"]
            trace = diagnostics.get("mafer") or {}
            captured.append(
                {
                    **case,
                    "payload": payload,
                    "session_id": session_id,
                    "http_status": response.status_code,
                    "started_at": started.isoformat(),
                    "completed_at": completed.isoformat(),
                    "wall_time_ms": round((completed - started).total_seconds() * 1000, 2),
                    "status": body["session"]["status"],
                    "outcome": diagnostics.get("outcome"),
                    "intent": diagnostics.get("query", {}).get("intent"),
                    "query_type": diagnostics.get("query", {}).get("query_type"),
                    "original_query": diagnostics.get("query", {}).get("original"),
                    "normalized_query": diagnostics.get("query", {}).get("normalized"),
                    "query_lattice": trace.get("query_lattice"),
                    "selected_sources": diagnostics.get("selected_sources", []),
                    "completion_order": diagnostics.get("connector_completion_order", []),
                    "per_source": aggregate_connectors(diagnostics.get("connectors", [])),
                    "candidate_admission": diagnostics.get("candidate_admission"),
                    "results": body["session"]["result_count"],
                    "unique": body["session"]["unique_count"],
                    "clusters": len(body.get("clusters", [])),
                    "duration_ms": body["session"]["duration_ms"],
                    "stop_reason": trace.get("stop_reason"),
                    "uncertainty": trace.get("uncertainty"),
                    "warnings": body["session"].get("warnings", []),
                    "top_results": [
                        {
                            "rank": index + 1,
                            "id": result["id"],
                            "source": result["source"],
                            "acquisition_mode": result["acquisition_mode"],
                            "canonical_url": result["canonical_url"],
                            "title": result.get("title"),
                            "text": (result.get("text") or "")[:500],
                            "score": result["score"],
                        }
                        for index, result in enumerate(body.get("results", [])[:5])
                    ],
                }
            )

    artifact = {
        "artifact": "MIRSAD v1.0 functional hardening live matrix",
        "observational_only": True,
        "captured_at": datetime.now(UTC).isoformat(),
        "api_root": API_ROOT,
        "source_states_before": source_states,
        "cases": captured,
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "cases": len(captured)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
