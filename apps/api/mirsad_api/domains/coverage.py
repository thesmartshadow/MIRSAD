from __future__ import annotations

from collections import Counter
from typing import Any

from ..schemas import CoverageGapReason

WEB_INDEXED_PLATFORMS = frozenset({"x", "threads", "reddit"})

ERROR_REASON = {
    "external_limit": CoverageGapReason.EXTERNAL_LIMIT,
    "access_limited": CoverageGapReason.EXTERNAL_LIMIT,
    "http_403": CoverageGapReason.EXTERNAL_LIMIT,
    "timeout": CoverageGapReason.TIMEOUT,
    "rate_limited": CoverageGapReason.RATE_LIMITED,
    "quota_exhausted": CoverageGapReason.RATE_LIMITED,
    "circuit_open": CoverageGapReason.CIRCUIT_OPEN,
    "restricted": CoverageGapReason.RESTRICTED,
    "auth_required": CoverageGapReason.RESTRICTED,
    "unconfigured": CoverageGapReason.UNCONFIGURED,
    "configuration_missing": CoverageGapReason.UNCONFIGURED,
    "disabled": CoverageGapReason.UNCONFIGURED,
    "unavailable": CoverageGapReason.UNAVAILABLE,
    "temporarily_unavailable": CoverageGapReason.UNAVAILABLE,
}

STOP_EXPLANATIONS = {
    "USER_LIMIT": "Stopped because the configured result limit was satisfied.",
    "SATISFIED": "Stopped because the available evidence satisfied the retrieval target.",
    "LOW_MARGINAL_GAIN": "Stopped because another round had low expected marginal evidence gain.",
    "BUDGET_EXHAUSTED": "Stopped after the bounded retrieval budget was exhausted.",
    "NO_SOURCES": "Stopped because no selected acquisition source could execute.",
    "TIME_BUDGET": "Stopped after the bounded search time budget was reached.",
    "REQUEST_BUDGET": "Stopped after the bounded connector request budget was reached.",
    "MAX_ROUNDS": "Stopped after the bounded retrieval round limit was reached.",
    "SOURCE_EXHAUSTION": "Stopped after all applicable selected sources were exhausted.",
    "NO_AVAILABLE_SOURCES": "Stopped because no selected acquisition source was available.",
}


def _reason_for_state(
    source: str,
    state: str,
    *,
    searxng_enabled: bool,
) -> CoverageGapReason:
    normalized = state.casefold()
    if source in WEB_INDEXED_PLATFORMS and not searxng_enabled:
        return CoverageGapReason.WEB_DISCOVERY_DISABLED
    if normalized == "restricted":
        return CoverageGapReason.RESTRICTED
    if normalized in {"unconfigured", "disabled", "configuration_missing"}:
        return CoverageGapReason.UNCONFIGURED
    if normalized in ERROR_REASON:
        return ERROR_REASON[normalized]
    return CoverageGapReason.NOT_SELECTED


def build_coverage_report(
    *,
    session_id: str,
    outcome_status: str,
    connector_states: dict[str, str],
    planned_sources: list[str],
    connector_rows: list[dict[str, Any]],
    acquisition_funnel: list[dict[str, Any]],
    final_platforms: list[str],
    final_acquisition_paths: list[tuple[str, ...]],
    historical_local_candidates: int,
    historical_final_flags: list[bool],
    historical_final_platforms: list[str],
    resource_plan: list[dict[str, Any]],
    stop_reason: str | None,
    searxng_enabled: bool,
) -> dict[str, Any]:
    planned = set(planned_sources)
    runs = {str(row["source"]): row for row in connector_rows}
    final_counts = Counter(final_platforms)
    planning_reasons = {
        str(row.get("source")): [str(value) for value in row.get("reasons", [])]
        for row in resource_plan
    }
    sources: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    selected_failures = False
    for source in sorted(connector_states):
        state = connector_states[source]
        run = runs.get(source)
        selected = source in planned
        executed = run is not None
        error = str((run or {}).get("error_category") or "").casefold()
        matched = int((run or {}).get("final_matching_results") or 0)
        admitted = int((run or {}).get("candidate_admitted_results") or 0)
        contributed = final_counts[source] > 0
        reason: CoverageGapReason | None = None
        detail: str | None = None
        if executed and error:
            reason = ERROR_REASON.get(error, CoverageGapReason.FAILED)
            detail = f"Execution ended with {error}."
            selected_failures = True
        elif executed and matched == 0:
            reason = CoverageGapReason.NO_MATCHES
            detail = "The source executed but produced no query matches."
        elif not selected:
            reason = _reason_for_state(source, state, searxng_enabled=searxng_enabled)
            detail = {
                CoverageGapReason.WEB_DISCOVERY_DISABLED: "Optional web discovery is disabled.",
                CoverageGapReason.RESTRICTED: (
                    "The connector requires restricted or approved access."
                ),
                CoverageGapReason.UNCONFIGURED: (
                    "The connector is not configured for this installation."
                ),
                CoverageGapReason.EXTERNAL_LIMIT: (
                    "The configured connector is currently limited by its external provider."
                ),
                CoverageGapReason.UNAVAILABLE: (
                    "The configured connector is currently unavailable."
                ),
                CoverageGapReason.TIMEOUT: (
                    "The configured connector is currently in a timed-out health state."
                ),
                CoverageGapReason.RATE_LIMITED: (
                    "The configured connector is currently rate limited."
                ),
                CoverageGapReason.CIRCUIT_OPEN: (
                    "The connector circuit is open after bounded external failures."
                ),
                CoverageGapReason.NOT_SELECTED: (
                    "The production planner did not select this source."
                ),
            }[reason]
        elif selected and not executed:
            reason = CoverageGapReason.NOT_SELECTED
            detail = "The source was planned but the bounded search stopped before execution."
        if reason is not None:
            gaps.append({"source": source, "reason": reason.value, "detail": detail or ""})
        sources.append(
            {
                "source": source,
                "selected": selected,
                "executed": executed,
                "contributed": contributed,
                "status": str((run or {}).get("status") or state).upper(),
                "acquisition_mode": (run or {}).get("acquisition_mode"),
                "reason": reason.value if reason else None,
                "detail": detail,
                "requests": int((run or {}).get("attempt_count") or 0),
                "fetched": int((run or {}).get("fetched_results") or 0),
                "matched": matched,
                "admitted": admitted,
                "final": final_counts[source],
                "planning_reasons": planning_reasons.get(source, []),
            }
        )
    funnel_by_path: dict[str, list[dict[str, Any]]] = {}
    for row in acquisition_funnel:
        funnel_by_path.setdefault(str(row.get("acquisition_path")), []).append(row)
    local_rows = funnel_by_path.get("LOCAL_MEMORY", [])
    historical_rows = funnel_by_path.get("HISTORICAL_INDEX", [])
    local_final = sum("LOCAL_MEMORY" in paths for paths in final_acquisition_paths)
    historical_final = sum(
        "HISTORICAL_INDEX" in paths or is_historical_local
        for paths, is_historical_local in zip(
            final_acquisition_paths, historical_final_flags, strict=True
        )
    )

    def has_live_path(paths: tuple[str, ...]) -> bool:
        return any(path not in {"LOCAL_MEMORY", "HISTORICAL_INDEX"} for path in paths)

    live_rows = [
        row
        for path, rows in funnel_by_path.items()
        if path not in {"LOCAL_MEMORY", "HISTORICAL_INDEX"}
        for row in rows
    ]
    lanes = [
        {
            "lane": "LIVE",
            "available": any(row["executed"] for row in sources),
            "executed": bool(runs),
            "contributed": any(has_live_path(paths) for paths in final_acquisition_paths),
            "candidates": sum(int(row.get("admitted") or 0) for row in live_rows),
            "final": sum(
                has_live_path(paths) for paths in final_acquisition_paths
            ),
            "platforms": sorted({str(row.get("platform")) for row in live_rows}),
        },
        {
            "lane": "LOCAL_MEMORY",
            "available": True,
            "executed": True,
            "contributed": local_final > 0,
            "candidates": sum(int(row.get("admitted") or 0) for row in local_rows),
            "final": local_final,
            "platforms": sorted({str(row.get("platform")) for row in local_rows}),
        },
        {
            "lane": "HISTORICAL",
            "available": bool(historical_rows) or historical_local_candidates > 0,
            "executed": bool(historical_rows) or historical_local_candidates > 0,
            "contributed": historical_final > 0,
            "candidates": historical_local_candidates
            + sum(int(row.get("admitted") or 0) for row in historical_rows),
            "final": historical_final,
            "platforms": sorted(
                {str(row.get("platform")) for row in historical_rows}
                | set(historical_final_platforms)
            ),
        },
    ]
    if selected_failures:
        coverage_status = "PARTIAL"
    elif gaps:
        coverage_status = "LIMITED"
    else:
        coverage_status = "COMPLETE_ATTEMPT"
    normalized_stop = stop_reason.upper() if stop_reason else None
    return {
        "session_id": session_id,
        "outcome_status": outcome_status,
        "coverage_status": coverage_status,
        "sources": sources,
        "lanes": lanes,
        "gaps": gaps,
        "represented_platforms": sorted(set(final_platforms)),
        "web_discovery": "ENABLED" if searxng_enabled else "DISABLED",
        "stop_reason": normalized_stop,
        "stop_explanation": STOP_EXPLANATIONS.get(normalized_stop or ""),
    }
