from __future__ import annotations

import json
from pathlib import Path

from mirsad_api.quality import evaluate_search_quality


def main() -> None:
    result = evaluate_search_quality()
    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    (report_dir / "search-quality.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metrics = result["metrics"]
    baseline = result["baseline_metrics"]
    hard = result["hard_evaluation"]
    hard_before = hard["baseline_metrics"]
    hard_after = hard["metrics"]
    signals = result["signal_checks"]
    languages = result["language_metrics"]
    components = result["score_component_statistics"]
    summary = "\n".join(
        [
            "# MIRSAD Search Quality Evaluation",
            "",
            f"- Fixture records: {result['fixture_records']}",
            f"- Queries: {result['query_count']}",
            f"- Mean Precision@5: {metrics['mean_precision_at_5']:.4f}",
            f"- Mean Precision@10: {metrics['mean_precision_at_10']:.4f}",
            "- Returned-set Precision@5: "
            f"{metrics['mean_returned_set_precision_at_5']:.4f}",
            "- Returned-set Precision@10: "
            f"{metrics['mean_returned_set_precision_at_10']:.4f}",
            f"- MRR: {metrics['mean_reciprocal_rank']:.4f}",
            "- Baseline returned-set Precision@5: "
            f"{baseline['mean_returned_set_precision_at_5']:.4f}",
            "- Hard-set Precision@5: "
            f"{hard_after['mean_precision_at_5']:.4f}",
            "- Hard-set returned-set Precision@5: "
            f"{hard_after['mean_returned_set_precision_at_5']:.4f}",
            f"- Hard-set MRR: {hard_after['mean_reciprocal_rank']:.4f}",
            f"- Duplicate reduction: {metrics['duplicate_reduction_rate']:.2%}",
            f"- Exact-phrase Precision@5: {metrics['exact_phrase_mean_precision_at_5']:.4f}",
            "- Exact-phrase returned-set Precision@5: "
            f"{metrics['exact_phrase_mean_returned_set_precision_at_5']:.4f}",
            f"- Title boost relevance delta: {signals['title_boost_relevance_delta']:.2f}",
            f"- Freshness final-score delta: {signals['freshness_final_score_delta']:.2f}",
            f"- Engagement final-score delta: {signals['engagement_final_score_delta']:.2f}",
            "- Relevant result outranks high-engagement collision: "
            f"{signals['relevant_beats_high_engagement_collision']}",
            "",
            "Precision@K uses K as its denominator. Returned-set precision is reported separately "
            "because the bounded fixture often returns fewer than K candidates. Ranking is "
            "deterministic and uses production query/scoring functions with a documented lexical "
            "BM25 proxy.",
        ]
    )
    (report_dir / "search-quality.md").write_text(summary + "\n", encoding="utf-8")
    relevance_report = "\n".join(
        [
            "# Relevance Improvement",
            "",
            "The same frozen fixtures and judgments were evaluated through the legacy "
            "and current pipelines.",
            "Precision@K uses K; returned-set precision divides by candidates returned up to K.",
            "",
            "| Metric | Before | After | Delta |",
            "|---|---:|---:|---:|",
            *(
                f"| {label} | {before:.4f} | {after:.4f} | {after - before:+.4f} |"
                for label, before, after in (
                    (
                        "Primary P@5",
                        baseline["mean_precision_at_5"],
                        metrics["mean_precision_at_5"],
                    ),
                    (
                        "Primary P@10",
                        baseline["mean_precision_at_10"],
                        metrics["mean_precision_at_10"],
                    ),
                    (
                        "Primary returned-set P@5",
                        baseline["mean_returned_set_precision_at_5"],
                        metrics["mean_returned_set_precision_at_5"],
                    ),
                    (
                        "Primary returned-set P@10",
                        baseline["mean_returned_set_precision_at_10"],
                        metrics["mean_returned_set_precision_at_10"],
                    ),
                    (
                        "Primary MRR",
                        baseline["mean_reciprocal_rank"],
                        metrics["mean_reciprocal_rank"],
                    ),
                    (
                        "Hard P@5",
                        hard_before["mean_precision_at_5"],
                        hard_after["mean_precision_at_5"],
                    ),
                    (
                        "Hard P@10",
                        hard_before["mean_precision_at_10"],
                        hard_after["mean_precision_at_10"],
                    ),
                    (
                        "Hard returned-set P@5",
                        hard_before["mean_returned_set_precision_at_5"],
                        hard_after["mean_returned_set_precision_at_5"],
                    ),
                    (
                        "Hard returned-set P@10",
                        hard_before["mean_returned_set_precision_at_10"],
                        hard_after["mean_returned_set_precision_at_10"],
                    ),
                    (
                        "Hard MRR",
                        hard_before["mean_reciprocal_rank"],
                        hard_after["mean_reciprocal_rank"],
                    ),
                )
            ),
            "",
            "## Interpretation",
            "",
            "Candidate generation now requires all tokens for two-token queries and 60% "
            "coverage for longer queries. Ranking uses bounded phrase, title, proximity, "
            "coverage, intent, and BM25 signals. Supporting signals are relevance-gated, so "
            "they cannot rescue a weak lexical match.",
            "",
            "The hard set intentionally retains ambiguous lexical collisions that cannot be "
            "resolved reliably without semantic context. These candidates remain visible "
            "rather than being silently over-filtered. Semantic reranking was not enabled "
            "because no measured benefit was established.",
            "",
            "## Language And Grouping Checks",
            "",
            "| Check | Precision | Recall / MRR |",
            "|---|---:|---:|",
            f"| Arabic returned-set P@5 / MRR | "
            f"{languages['arabic']['mean_returned_set_precision_at_5']:.4f} | "
            f"{languages['arabic']['mean_reciprocal_rank']:.4f} |",
            f"| English returned-set P@5 / MRR | "
            f"{languages['english']['mean_returned_set_precision_at_5']:.4f} | "
            f"{languages['english']['mean_reciprocal_rank']:.4f} |",
            f"| Mixed-language returned-set P@5 / MRR | "
            f"{languages['mixed']['mean_returned_set_precision_at_5']:.4f} | "
            f"{languages['mixed']['mean_reciprocal_rank']:.4f} |",
            f"| Judged duplicate pairs | "
            f"{metrics['duplicate_pair_quality']['precision']:.4f} | "
            f"{metrics['duplicate_pair_quality']['recall']:.4f} |",
            f"| Judged cluster pairs | "
            f"{metrics['cluster_pair_quality']['precision']:.4f} | "
            f"{metrics['cluster_pair_quality']['recall']:.4f} |",
            "",
            "## Score Calibration",
            "",
            "| Component | Min | Max | Mean | Median | Stddev | P10 | P25 | P75 | P90 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            *(
                f"| {name} | {stats['min']:.2f} | {stats['max']:.2f} | "
                f"{stats['mean']:.2f} | {stats['median']:.2f} | "
                f"{stats['stddev']:.2f} | {stats['p10']:.2f} | {stats['p25']:.2f} | "
                f"{stats['p75']:.2f} | {stats['p90']:.2f} |"
                for name, stats in components.items()
            ),
            "",
            "Source Confidence, Cross-Source Presence, and Novelty are constant in the hard "
            "ranking fixture. Their zero variance is a fixture limitation, not evidence that "
            "these signals are constant in stored searches.",
            "",
            "## Residual Errors",
            "",
            *(
                f"- `{error['category']}`: query `{error['query']}` returned "
                f"`{error['document']}` within the first five candidates."
                for error in hard["error_analysis"]
            ),
        ]
    )
    (report_dir / "relevance-improvement.md").write_text(
        relevance_report + "\n", encoding="utf-8"
    )
    print(summary)


if __name__ == "__main__":
    main()
