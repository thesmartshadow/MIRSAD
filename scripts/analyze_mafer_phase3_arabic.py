from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from mirsad_api.domains.query import process_query
from mirsad_api.mafer.intent import QueryIntentAnalyzer
from mirsad_api.mafer.lattice import build_query_lattice

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT = ROOT / "apps/api/tests/fixtures/mafer_phase3_development.json"


def main() -> None:
    payload = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
    cases = [case for case in payload["cases"] if case["language"] in {"arabic", "mixed"}]
    totals = {
        "possible_relevant": 0,
        "discovered": 0,
        "canonical": 0,
        "admitted": 0,
        "semantic_opportunity": 0,
        "top_10": 0,
    }
    output_cases: list[dict[str, Any]] = []
    for case in cases:
        final = case["rounds"][-1]
        processed = process_query(case["query"], exact_phrase=case["class"] == "exact_phrase")
        fingerprint = QueryIntentAnalyzer().analyze(
            processed,
            explicit_time_range=case["time_range"],
        )
        lattice = build_query_lattice(processed, fingerprint, max_variants=8)
        stage_values = {
            "possible_relevant": int(case["possible_relevant"]),
            "discovered": int(final["discovered_relevant"]),
            "canonical": int(final["canonical_relevant"]),
            "admitted": int(final["admitted_relevant"]),
            "semantic_opportunity": int(final["semantic_relevant"]),
            "top_10": sum(int(rank) <= 10 for rank in final["relevant_ranks"]),
        }
        for key, value in stage_values.items():
            totals[key] += value
        losses = {
            "source_coverage_or_discovery": stage_values["possible_relevant"]
            - stage_values["discovered"],
            "canonicalization_or_duplicate_collapse": stage_values["discovered"]
            - stage_values["canonical"],
            "candidate_admission": stage_values["canonical"] - stage_values["admitted"],
            "semantic_opportunity": stage_values["admitted"] - stage_values["semantic_opportunity"],
            "final_top_10": stage_values["semantic_opportunity"] - stage_values["top_10"],
        }
        largest_loss = max(losses.values())
        output_cases.append(
            {
                "id": case["id"],
                "query": case["query"],
                "query_class": case["class"],
                "stages": stage_values,
                "losses": losses,
                "dominant_loss_stage": max(losses, key=losses.get) if largest_loss else "NONE",
                "production_lattice": [
                    {
                        "type": variant.transformation.value,
                        "text": variant.text,
                        "confidence": variant.confidence,
                        "drift_risk": variant.drift_risk,
                        "round": variant.round_created,
                    }
                    for variant in lattice.variants
                ],
                "useful_variant_labels": case["useful_variants"],
            }
        )
    report = {
        "schema": "mirsad.mafer-phase3-arabic-loss-funnel",
        "version": "1.0",
        "development_sha256": hashlib.sha256(DEVELOPMENT.read_bytes()).hexdigest(),
        "cases": len(cases),
        "totals": totals,
        "losses": {
            "source_coverage_or_discovery": totals["possible_relevant"] - totals["discovered"],
            "canonicalization_or_duplicate_collapse": totals["discovered"] - totals["canonical"],
            "candidate_admission": totals["canonical"] - totals["admitted"],
            "semantic_opportunity": totals["admitted"] - totals["semantic_opportunity"],
            "final_top_10": totals["semantic_opportunity"] - totals["top_10"],
        },
        "cases_detail": output_cases,
        "interpretation": (
            "Stage labels identify where judged items disappear; they do not infer why an "
            "external source failed to discover an item."
        ),
    }
    output = ROOT / "reports/mafer-phase3-arabic-funnel.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
