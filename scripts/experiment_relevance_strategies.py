from __future__ import annotations

import argparse
import gc
import json
import resource
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
from analyze_holdout_relevance import (
    DEFAULT_WEIGHTS,
    _aggregate,
    _fts_connection,
    _fts_scores,
    _metrics,
)
from fastembed import TextEmbedding

from mirsad_api.domains.query import process_query, tokenize
from mirsad_api.domains.ranking import (
    calculate_score,
    freshness_score,
    relevance_score,
    spam_penalty,
)

ROOT = Path(__file__).resolve().parents[1]
TUNING_DOCUMENTS = ROOT / "apps/api/tests/fixtures/relevance_tuning_documents.json"
TUNING_JUDGMENTS = ROOT / "apps/api/tests/fixtures/relevance_tuning_judgments.json"
MODEL_CACHE = Path("/tmp/mirsad-semantic-models")
MODELS = {
    "minilm": {
        "name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dimensions": 384,
        "declared_size_gib": 0.22,
    },
    "mpnet": {
        "name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "dimensions": 768,
        "declared_size_gib": 1.0,
    },
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def _rrf(rank_a: int, rank_b: int, *, k: int) -> float:
    return 1 / (k + rank_a) + 1 / (k + rank_b)


def _strategy_metrics(cases: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    case_metrics = [
        {"metrics": _metrics(case["rankings"][strategy], set(case["relevant"]))} for case in cases
    ]
    return _aggregate(case_metrics)


def evaluate_model(model_key: str) -> dict[str, Any]:
    definition = MODELS[model_key]
    corpus = _load(TUNING_DOCUMENTS)
    judgments = _load(TUNING_JUDGMENTS)["queries"]
    documents = corpus["documents"]
    evaluation_now = datetime.fromisoformat(
        corpus["evaluation_now"].replace("Z", "+00:00")
    ).astimezone(UTC)
    fts, row_ids = _fts_connection(documents)

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    initialization_started = time.perf_counter()
    model = TextEmbedding(model_name=definition["name"], cache_dir=str(MODEL_CACHE), threads=8)
    initialization_ms = (time.perf_counter() - initialization_started) * 1000
    document_texts = [f"{document['title']}. {document['text']}" for document in documents]
    encoding_started = time.perf_counter()
    document_vectors = list(model.embed(document_texts, batch_size=32))
    document_encoding_ms = (time.perf_counter() - encoding_started) * 1000
    vectors_by_id = {
        document["id"]: np.asarray(vector, dtype=np.float32)
        for document, vector in zip(documents, document_vectors, strict=True)
    }
    rss_loaded = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    cases: list[dict[str, Any]] = []
    query_encoding_samples: list[float] = []
    ranking_samples: list[float] = []

    for judgment in judgments:
        query = process_query(judgment["query"], exact_phrase=judgment["exact_phrase"])
        query_started = time.perf_counter()
        query_vector = np.asarray(next(model.query_embed(judgment["query"])), dtype=np.float32)
        query_encoding_samples.append((time.perf_counter() - query_started) * 1000)
        fts_strengths, fts_normalized = _fts_scores(fts, row_ids, query)
        rows: list[dict[str, Any]] = []
        ranking_started = time.perf_counter()
        for document in documents:
            content_tokens = set(tokenize(f"{document['title']} {document['text']}"))
            if not set(query.tokens).intersection(content_tokens):
                continue
            coverage = len(content_tokens & set(query.tokens)) / max(1, len(query.tokens))
            baseline = calculate_score(
                query=query,
                title=document["title"],
                text=document["text"],
                canonical_url=document["url"],
                published_at=evaluation_now - timedelta(hours=document["age_hours"]),
                engagement=document["engagement"],
                source_confidence=document["source_confidence"],
                cross_source_presence=document["cross_source_presence"],
                novelty=document["novelty"],
                bm25_normalized=coverage * 100,
                weights=DEFAULT_WEIGHTS,
                now=evaluation_now,
            )
            lexical_relevance, _ = relevance_score(
                query,
                document["title"],
                document["text"],
                bm25_normalized=fts_normalized.get(document["id"], 0),
                canonical_url=document["url"],
            )
            semantic_cosine = _cosine(query_vector, vectors_by_id[document["id"]])
            semantic_score = max(0.0, min(100.0, (semantic_cosine + 1) * 50))
            freshness = freshness_score(
                evaluation_now - timedelta(hours=document["age_hours"]), now=evaluation_now
            )
            secondary_quality = (
                0.20 * freshness
                + 0.15 * document["engagement"]
                + 0.10 * document["source_confidence"]
                + 0.10 * document["cross_source_presence"]
                + 0.10 * document["novelty"]
            ) / 0.65
            rows.append(
                {
                    "id": document["id"],
                    "published": (
                        evaluation_now - timedelta(hours=document["age_hours"])
                    ).timestamp(),
                    "baseline_final": baseline.final_score,
                    "lexical_relevance": lexical_relevance,
                    "bm25": fts_normalized.get(document["id"], 0),
                    "semantic_cosine": semantic_cosine,
                    "semantic_score": semantic_score,
                    "secondary_quality": secondary_quality,
                    "spam_penalty": spam_penalty(
                        document["title"], document["text"], document["url"]
                    ),
                }
            )

        def ordered(key, candidates=rows) -> list[str]:
            return [row["id"] for row in sorted(candidates, key=key, reverse=True)]

        baseline_ranking = ordered(lambda row: (row["baseline_final"], row["published"], row["id"]))
        lexical_ranking = ordered(
            lambda row: (
                row["lexical_relevance"],
                row["bm25"],
                row["baseline_final"],
                row["id"],
            )
        )
        semantic_ranking = ordered(
            lambda row: (row["semantic_cosine"], row["lexical_relevance"], row["id"])
        )
        lexical_rank = {identifier: rank for rank, identifier in enumerate(lexical_ranking, 1)}
        semantic_rank = {identifier: rank for rank, identifier in enumerate(semantic_ranking, 1)}
        rankings = {
            "current_baseline": baseline_ranking,
            "improved_lexical": lexical_ranking,
            "semantic_only": semantic_ranking,
        }
        for semantic_weight in (0.25, 0.5, 0.75):
            name = f"weighted_semantic_{semantic_weight:.2f}"
            rankings[name] = ordered(
                lambda row, weight=semantic_weight: (
                    (1 - weight) * row["lexical_relevance"] + weight * row["semantic_score"],
                    row["baseline_final"],
                    row["id"],
                )
            )
        for semantic_weight in (0.5, 0.75, 1.0):
            for quality_budget in (0.01, 0.02, 0.05, 0.10, 0.15):
                name = f"bounded_s{semantic_weight:.2f}_q{quality_budget:.2f}"

                def bounded_key(row, semantic=semantic_weight, quality=quality_budget):
                    combined_relevance = (1 - semantic) * row["lexical_relevance"] + semantic * row[
                        "semantic_score"
                    ]
                    eligibility = (combined_relevance / 100) ** 2
                    final = (
                        (1 - quality) * combined_relevance
                        + quality * row["secondary_quality"] * eligibility
                        - row["spam_penalty"]
                    )
                    return (final, combined_relevance, row["id"])

                rankings[name] = ordered(bounded_key)
        for k in (20, 60):
            rankings[f"rrf_k{k}"] = ordered(
                lambda row, constant=k, lex=lexical_rank, sem=semantic_rank: (
                    _rrf(lex[row["id"]], sem[row["id"]], k=constant),
                    row["semantic_cosine"],
                    row["id"],
                )
            )
        # The corpus is small, but this explicitly represents lexical top-20 followed by semantic
        # reranking. Candidates outside the first stage retain lexical order after the reranked set.
        lexical_top = set(lexical_ranking[:20])
        rankings["two_stage_semantic_20"] = [
            *[identifier for identifier in semantic_ranking if identifier in lexical_top],
            *[identifier for identifier in lexical_ranking if identifier not in lexical_top],
        ]
        ranking_samples.append((time.perf_counter() - ranking_started) * 1000)
        cases.append(
            {
                "id": judgment["id"],
                "query": judgment["query"],
                "language": judgment["language"],
                "query_class": judgment["query_class"],
                "relevant": judgment["relevant"],
                "rankings": rankings,
                "semantic_scores": {row["id"]: round(row["semantic_cosine"], 6) for row in rows},
            }
        )

    strategies = list(cases[0]["rankings"])
    strategy_metrics = {
        strategy: {
            "overall": _strategy_metrics(cases, strategy),
            "language": {
                language: _strategy_metrics(
                    [case for case in cases if case["language"] == language], strategy
                )
                for language in ("arabic", "english", "mixed")
            },
        }
        for strategy in strategies
    }
    per_query = []
    for case in cases:
        per_query.append(
            {
                "id": case["id"],
                "query": case["query"],
                "language": case["language"],
                "query_class": case["query_class"],
                "relevant": case["relevant"],
                "strategies": {
                    strategy: _metrics(ranking, set(case["relevant"]))
                    for strategy, ranking in case["rankings"].items()
                },
                "semantic_scores": case["semantic_scores"],
            }
        )
    result = {
        "schema": "mirsad.relevance-strategy-experiment",
        "version": "1.0",
        "dataset": "relevance_tuning",
        "documents": len(documents),
        "queries": len(judgments),
        "model": definition,
        "performance": {
            "model_initialization_ms": round(initialization_ms, 2),
            "document_encoding_ms": round(document_encoding_ms, 2),
            "document_encoding_per_item_ms": round(document_encoding_ms / len(documents), 4),
            "query_encoding_mean_ms": round(mean(query_encoding_samples), 4),
            "reranking_mean_ms": round(mean(ranking_samples), 4),
            "peak_rss_before_kib": rss_before,
            "peak_rss_loaded_kib": rss_loaded,
            "peak_rss_delta_kib": max(0, rss_loaded - rss_before),
        },
        "strategy_metrics": strategy_metrics,
        "per_query": per_query,
    }
    fts.close()
    del model
    gc.collect()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_model(args.model)
    output = args.output or ROOT / "reports" / f"relevance-strategy-{args.model}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "model": result["model"],
                "performance": result["performance"],
                "strategy_metrics": result["strategy_metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
