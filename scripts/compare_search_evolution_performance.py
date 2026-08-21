from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def percent(before: float, after: float) -> float:
    return round(((after - before) / before) * 100, 2) if before else 0.0


baseline = json.loads(Path("reports/search-evolution-baseline.json").read_text())
after = json.loads(Path("/tmp/search-evolution-after.json").read_text())
baseline_by_case = {row["case"]: row for row in baseline["observations"]}
after_by_case = {row["case"]: row for row in after["observations"]}
cases: dict[str, object] = {}
for name in baseline_by_case:
    before = baseline_by_case[name]
    current = after_by_case[name]
    before_semantic = float(before["semantic"]["duration_ms"])
    after_semantic = float(current["semantic"]["duration_ms"])
    before_wall = float(before["wall_ms"])
    after_wall = float(current["wall_ms"])
    cases[name] = {
        "semantic_ms": {
            "baseline": before_semantic,
            "after": after_semantic,
            "change_percent": percent(before_semantic, after_semantic),
        },
        "api_wall_ms": {
            "baseline": before_wall,
            "after": after_wall,
            "change_percent": percent(before_wall, after_wall),
        },
        "rss_after_mib": {
            "baseline": before["rss_after_mib"],
            "after": current["rss_after_mib"],
        },
        "cache_hits": current["semantic"]["cache_hits"],
        "cache_misses": current["semantic"]["cache_misses"],
        "semantic_profile_ms": current["semantic"].get("timings_ms", {}),
        "embedding_batch_size": current["semantic"].get("batch_size", 0),
    }

payload = {
    "schema": "mirsad.search-evolution-performance",
    "version": "1.1.0",
    "captured_at": datetime.now(UTC).isoformat(),
    "operator_database_used": False,
    "cases": cases,
    "decisions": {
        "persistent_embedding_cache": "NOT_IMPLEMENTED",
        "reason": (
            "The existing bounded in-process content cache and batch encoder already reduce "
            "warm document generation to zero; a new persistent vector store did not clear "
            "the evidence gate."
        ),
        "batching": "PRESERVED_BOUNDED_MAX_32",
        "ranking_semantics": "UNCHANGED",
        "perceived_speed": "SSE_PROGRESS_IMPLEMENTED",
    },
    "interpretation": (
        "Cold-run variance is dominated by local model initialization. Warm-path changes within "
        "a few milliseconds are measurement noise and are not claimed as compute improvement."
    ),
}
Path("reports/search-evolution-performance.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
