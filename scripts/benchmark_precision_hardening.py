#!/usr/bin/env python3
"""Measure semantic preparation overlap without touching application data."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from mirsad_api.domains.query import process_query  # noqa: E402
from mirsad_api.domains.semantic import (  # noqa: E402
    LocalSemanticRanker,
    SemanticDocument,
    score_in_worker,
)
from mirsad_api.services.semantic_preparation import (  # noqa: E402
    SemanticPreparationCoordinator,
)


def rss_mb() -> float:
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    value = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
    return round(int(value.split()[1]) / 1024, 2)


def clear_cache(ranker: LocalSemanticRanker) -> None:
    with ranker._lock:
        ranker._embeddings.clear()


async def benchmark(network_wait_ms: int) -> dict[str, object]:
    ranker = LocalSemanticRanker(
        enabled=True,
        cache_dir=str(ROOT / "data" / "models"),
        local_files_only=True,
        embedding_cache_size=5000,
    )
    documents = [
        SemanticDocument(
            key=index,
            title=f"Precision hardening evidence record {index}",
            text=(
                "وزارة التخطيط تنشر تقريرا عاما عن بغداد والتحول الرقمي "
                if index % 2 == 0
                else "Linux kernel security maintainers publish a technical advisory "
            )
            + f"with deterministic bounded semantic candidate number {index}.",
        )
        for index in range(20)
    ]
    query = process_query("الذكاء الاصطناعي في العراق")
    warm = ranker.score(
        process_query("model warmup"),
        [SemanticDocument(key=-1, title="Warmup", text="Local model initialization")],
    )
    if warm.state != "ready":
        return {
            "schema": "mirsad.precision-hardening-performance",
            "gate": "unavailable",
            "detail": warm.detail,
        }
    clear_cache(ranker)
    rss_before = rss_mb()

    sequential_started = perf_counter()
    await asyncio.sleep(network_wait_ms / 1000)
    sequential_scores = await score_in_worker(ranker, query, documents)
    sequential_total_ms = (perf_counter() - sequential_started) * 1000
    sequential_rss = rss_mb()

    clear_cache(ranker)
    overlap_started = perf_counter()
    collection_started = perf_counter()
    coordinator = SemanticPreparationCoordinator(ranker, max_candidates=20)
    await coordinator.submit(documents)
    await asyncio.sleep(network_wait_ms / 1000)
    collection_finished = perf_counter()
    preparation = await coordinator.finish(
        collection_started=collection_started,
        collection_finished=collection_finished,
    )
    overlap_scores = await score_in_worker(ranker, query, documents)
    overlap_total_ms = (perf_counter() - overlap_started) * 1000
    overlap_rss = rss_mb()

    sequential_order = sorted(
        sequential_scores.scores,
        key=sequential_scores.scores.get,
        reverse=True,
    )
    overlap_order = sorted(
        overlap_scores.scores,
        key=overlap_scores.scores.get,
        reverse=True,
    )
    equivalent = (
        sequential_scores.scores == overlap_scores.scores
        and sequential_scores.similarities == overlap_scores.similarities
        and sequential_order == overlap_order
    )
    reduction_ms = sequential_total_ms - overlap_total_ms
    reduction_percent = 100 * reduction_ms / sequential_total_ms
    for _ in range(3):
        repeated = SemanticPreparationCoordinator(ranker, max_candidates=20)
        await repeated.submit(documents)
        await repeated.finish(collection_started=perf_counter(), collection_finished=perf_counter())
        await score_in_worker(ranker, query, documents)
    steady_rss = rss_mb()
    steady_growth_mb = steady_rss - overlap_rss
    memory_bounded = steady_growth_mb <= 10
    meaningful = (
        equivalent
        and reduction_percent >= 15
        and overlap_scores.cache_misses == 0
        and memory_bounded
    )
    return {
        "schema": "mirsad.precision-hardening-performance",
        "network_wait_ms": network_wait_ms,
        "candidate_count": len(documents),
        "model": ranker.model_name,
        "model_version": ranker.model_version,
        "v1_1_sequential": {
            "total_ms": round(sequential_total_ms, 2),
            "semantic_critical_path_ms": sequential_scores.duration_ms,
            "ranking_cache_hits": sequential_scores.cache_hits,
            "ranking_cache_misses": sequential_scores.cache_misses,
        },
        "v1_1_1_overlap": {
            "total_ms": round(overlap_total_ms, 2),
            "precompute_wall_ms": preparation.wall_ms,
            "overlap_window_ms": preparation.overlap_window_ms,
            "semantic_work_hidden_ms": preparation.hidden_work_ms,
            "semantic_critical_path_ms": overlap_scores.duration_ms,
            "ranking_cache_hits": overlap_scores.cache_hits,
            "ranking_cache_misses": overlap_scores.cache_misses,
        },
        "comparison": {
            "critical_path_reduction_ms": round(reduction_ms, 2),
            "critical_path_reduction_percent": round(reduction_percent, 2),
            "scores_exact": sequential_scores.scores == overlap_scores.scores,
            "similarities_exact": sequential_scores.similarities == overlap_scores.similarities,
            "order_exact": sequential_order == overlap_order,
            "meaningful_improvement": meaningful,
            "memory_bounded": memory_bounded,
        },
        "memory": {
            "rss_before_mb": rss_before,
            "rss_after_sequential_mb": sequential_rss,
            "rss_after_overlap_mb": overlap_rss,
            "overlap_delta_mb": round(overlap_rss - sequential_rss, 2),
            "rss_after_three_repeat_jobs_mb": steady_rss,
            "steady_state_growth_mb": round(steady_growth_mb, 2),
            "cache_bound": ranker.embedding_cache_size,
            "cache_entries": len(ranker._embeddings),
        },
        "gate": "ship" if meaningful else "revert",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network-wait-ms", type=int, default=1400)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "precision-hardening-performance.json",
    )
    arguments = parser.parse_args()
    result = asyncio.run(benchmark(max(0, arguments.network_wait_ms)))
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.get("comparison", result)))
    if result.get("gate") != "ship":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
