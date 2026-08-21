from __future__ import annotations

import json
import resource
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from mirsad_api.domains.query import fts_query, normalize_text, process_query
from mirsad_api.domains.ranking import calculate_score, relevance_score
from mirsad_api.domains.semantic import LocalSemanticRanker, SemanticDocument

ROOT = Path(__file__).resolve().parents[1]
SIZES = (100, 1_000, 5_000, 10_000)
WEIGHTS = {
    "relevance": 0.35,
    "freshness": 0.20,
    "engagement": 0.15,
    "source_confidence": 0.10,
    "cross_source_presence": 0.10,
    "novelty": 0.10,
}


def _documents(size: int) -> list[tuple[int, str, str]]:
    return [
        (
            index,
            f"Artificial intelligence regulation record {index}",
            (
                "A substantive policy assessment of artificial intelligence regulation, "
                "risk controls, education, and public accountability."
                if index % 4 == 0
                else "Artificial intelligence appears in a technology listing while regulation "
                "is mentioned in a separate administrative context."
            ),
        )
        for index in range(1, size + 1)
    ]


def _fts(documents: list[tuple[int, str, str]]) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE VIRTUAL TABLE records USING fts5("
        "title, text, normalized_title, normalized_text, "
        "tokenize='unicode61 remove_diacritics 2')"
    )
    connection.executemany(
        "INSERT INTO records(rowid, title, text, normalized_title, normalized_text) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (identifier, title, text, normalize_text(title), normalize_text(text))
            for identifier, title, text in documents
        ],
    )
    return connection


def benchmark() -> dict[str, object]:
    query = process_query("artificial intelligence regulation")
    ranker = LocalSemanticRanker(
        enabled=True,
        cache_dir=str(ROOT / "data/models"),
        local_files_only=True,
        threads=4,
    )
    rows: list[dict[str, float | int]] = []
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    now = datetime(2026, 8, 9, tzinfo=UTC)
    for size in SIZES:
        documents = _documents(size)
        by_id = {identifier: (title, text) for identifier, title, text in documents}
        connection = _fts(documents)
        started = time.perf_counter()
        fts_rows = connection.execute(
            "SELECT rowid, bm25(records, 4.0, 1.0, 4.0, 1.0) FROM records WHERE records MATCH ?",
            (fts_query(query),),
        ).fetchall()
        retrieval_ms = (time.perf_counter() - started) * 1000
        strengths = {int(identifier): max(0.0, -float(score)) for identifier, score in fts_rows}
        maximum = max(strengths.values(), default=1.0)

        started = time.perf_counter()
        lexical = []
        for identifier, strength in strengths.items():
            title, text = by_id[identifier]
            bm25 = 100 * strength / maximum
            relevance, _matched = relevance_score(
                query,
                title,
                text,
                bm25_normalized=bm25,
                canonical_url=f"https://benchmark.invalid/{identifier}",
            )
            lexical.append((relevance, bm25, identifier))
        lexical.sort(reverse=True)
        top = lexical[:20]
        lexical_ms = (time.perf_counter() - started) * 1000
        semantic_documents = [
            SemanticDocument(key=identifier, title=by_id[identifier][0], text=by_id[identifier][1])
            for _relevance, _bm25, identifier in top
        ]
        cold = ranker.score(query, semantic_documents)
        warm = ranker.score(query, semantic_documents)

        started = time.perf_counter()
        for _lexical_relevance, bm25, identifier in top:
            title, text = by_id[identifier]
            calculate_score(
                query=query,
                title=title,
                text=text,
                canonical_url=f"https://benchmark.invalid/{identifier}",
                published_at=now,
                engagement=50,
                source_confidence=70,
                bm25_normalized=bm25,
                semantic_relevance=cold.scores[identifier],
                semantic_similarity=cold.similarities[identifier],
                weights=WEIGHTS,
                now=now,
            )
        final_scoring_ms = (time.perf_counter() - started) * 1000
        rows.append(
            {
                "documents": size,
                "fts_matches": len(fts_rows),
                "retrieval_ms": round(retrieval_ms, 2),
                "lexical_feature_ms": round(lexical_ms, 2),
                "cold_semantic_ms": cold.duration_ms,
                "warm_semantic_ms": warm.duration_ms,
                "final_scoring_ms": round(final_scoring_ms, 2),
                "cold_total_ms": round(
                    retrieval_ms + lexical_ms + cold.duration_ms + final_scoring_ms, 2
                ),
                "warm_total_ms": round(
                    retrieval_ms + lexical_ms + warm.duration_ms + final_scoring_ms, 2
                ),
                "warm_cache_hits": warm.cache_hits,
                "reranked_candidates": len(top),
            }
        )
        connection.close()
    return {
        "schema": "mirsad.relevance-performance",
        "version": "1.0",
        "model": ranker.model_name,
        "candidate_limit": 20,
        "production_search_result_cap": 200,
        "peak_rss_delta_kib": max(
            0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - rss_before
        ),
        "observations": rows,
    }


def main() -> None:
    result = benchmark()
    reports = ROOT / "reports"
    (reports / "relevance-performance.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Relevance Performance",
        "",
        "Local CPU measurements only; connector network time is excluded.",
        "",
        "| Documents | FTS | Lexical | Semantic cold | Semantic warm | Total cold | Total warm |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *(
            f"| {row['documents']} | {row['retrieval_ms']:.2f} ms | "
            f"{row['lexical_feature_ms']:.2f} ms | {row['cold_semantic_ms']:.2f} ms | "
            f"{row['warm_semantic_ms']:.2f} ms | {row['cold_total_ms']:.2f} ms | "
            f"{row['warm_total_ms']:.2f} ms |"
            for row in result["observations"]
        ),
        "",
        f"Peak observed RSS increase: {result['peak_rss_delta_kib'] / 1024:.1f} MiB.",
        "Semantic work is bounded to 20 candidates. Production collection is capped at 200; "
        "the 1,000-10,000 rows are lexical scaling stress observations, not normal session sizes.",
    ]
    (reports / "relevance-performance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
