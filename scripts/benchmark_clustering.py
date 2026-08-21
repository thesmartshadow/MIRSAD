from __future__ import annotations

import argparse
import json
import resource
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

from mirsad_api.config import Settings
from mirsad_api.domains.clustering import build_cluster_candidate_plan, cluster_items
from mirsad_api.domains.deduplication import DeduplicationItem
from mirsad_api.domains.query import tokenize
from mirsad_api.domains.semantic import LocalSemanticRanker, SemanticDocument

ROOT = Path(__file__).resolve().parents[1]


def _documents(count: int) -> list[DeduplicationItem]:
    items: list[DeduplicationItem] = []
    story_documents = (count // 10) * 3
    for offset in range(story_documents):
        story = offset // 3
        variant = offset % 3
        event = f"atlasstory{story}"
        titles = (
            f"Ministry launches {event} satellite",
            f"{event} satellite launched after ministry announcement",
            f"Public coverage of the {event} launch",
        )
        texts = (
            f"The ministry launched the {event} satellite from Basra.",
            f"The {event} spacecraft lifted off from Basra after the announcement.",
            f"A report explains the ministry's {event} satellite launch in Basra.",
        )
        items.append(
            DeduplicationItem(
                key=offset + 1,
                source=("rss", "telegram", "youtube")[variant],
                canonical_url=f"https://source{variant}.example/{event}/{variant}",
                title=titles[variant],
                text=texts[variant],
                published_at=datetime(2026, 1, 1, tzinfo=UTC)
                + timedelta(hours=story, minutes=variant),
            )
        )
    for offset in range(story_documents, count):
        items.append(
            DeduplicationItem(
                key=offset + 1,
                source="github" if offset % 2 else "hacker_news",
                canonical_url=f"https://example.test/unrelated/{offset}",
                title=f"Technology project uniqueitem{offset}",
                text=f"An unrelated technology record about uniquecontext{offset}.",
                published_at=datetime(2026, 1, 1, tzinfo=UTC)
                + timedelta(hours=offset),
            )
        )
    return items


def _memory_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def run(sizes: list[int], *, semantic: bool) -> dict[str, object]:
    settings = Settings()
    cache_dir = Path(settings.semantic_model_cache_dir)
    if not cache_dir.is_absolute():
        cache_dir = ROOT / cache_dir
    ranker = LocalSemanticRanker(
        enabled=semantic,
        model_name=settings.semantic_model_name,
        model_version=settings.semantic_model_version,
        cache_dir=str(cache_dir),
        local_files_only=True,
        threads=settings.semantic_threads,
    )
    measurements: list[dict[str, object]] = []
    for size in sizes:
        items = _documents(size)
        memory_before = _memory_mib()
        total_started = perf_counter()
        blocking_started = perf_counter()
        plan = build_cluster_candidate_plan(
            items,
            query_tokens=tokenize("technology"),
        )
        blocking_ms = (perf_counter() - blocking_started) * 1000
        semantic_started = perf_counter()
        semantic_scores = ranker.cluster_similarities(
            [
                SemanticDocument(key=item.key, title=item.title, text=item.text)
                for item in items
                if item.key in plan.representative_keys
            ],
            plan.pairs,
        )
        semantic_wall_ms = (perf_counter() - semantic_started) * 1000
        construction_started = perf_counter()
        clusters = cluster_items(
            items,
            query_tokens=tokenize("technology"),
            semantic_similarities=semantic_scores.similarities,
            candidate_plan=plan,
        )
        construction_ms = (perf_counter() - construction_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000
        all_possible_pairs = size * (size - 1) // 2
        measurements.append(
            {
                "records": size,
                "candidate_pairs": len(plan.pairs),
                "all_possible_pairs": all_possible_pairs,
                "candidate_fraction": round(
                    len(plan.pairs) / all_possible_pairs if all_possible_pairs else 0, 8
                ),
                "lexical_block_pairs": plan.lexical_block_pairs,
                "temporal_block_pairs": plan.temporal_block_pairs,
                "capped_pairs": plan.capped_pairs,
                "candidate_blocking_ms": round(blocking_ms, 3),
                "semantic_wall_ms": round(semantic_wall_ms, 3),
                "semantic_reported_ms": semantic_scores.duration_ms,
                "semantic_state": semantic_scores.state,
                "embedding_cache_hits": semantic_scores.cache_hits,
                "embedding_cache_misses": semantic_scores.cache_misses,
                "cluster_construction_ms": round(construction_ms, 3),
                "total_clustering_ms": round(total_ms, 3),
                "clusters": len(clusters),
                "largest_cluster": max(len(cluster.members) for cluster in clusters),
                "suspicious_clusters": sum(cluster.suspicious for cluster in clusters),
                "process_peak_rss_mib": round(_memory_mib(), 2),
                "peak_rss_growth_mib": round(max(0.0, _memory_mib() - memory_before), 2),
            }
        )
    return {
        "schema": "mirsad.clustering-performance",
        "version": "1.0",
        "semantic_enabled": semantic,
        "semantic_model": settings.semantic_model_name if semantic else None,
        "semantic_model_version": settings.semantic_model_version if semantic else None,
        "method": (
            "Synthetic bounded story blocks; peak RSS is process-level observational evidence, "
            "not a formal leak analysis."
        ),
        "measurements": measurements,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark bounded MIRSAD clustering")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/clustering-performance.json")
    parser.add_argument("--no-semantic", action="store_true")
    args = parser.parse_args()
    payload = run([100, 200, 500, 1000], semantic=not args.no_semantic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["measurements"], indent=2))


if __name__ == "__main__":
    main()
