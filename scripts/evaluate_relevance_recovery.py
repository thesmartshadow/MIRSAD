from __future__ import annotations

import json
import resource
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from analyze_holdout_relevance import (
    CORPUS_PATH,
    DEFAULT_WEIGHTS,
    JUDGMENTS_PATH,
    _fts_connection,
    _fts_scores,
    verify_frozen_holdout,
)

from mirsad_api.domains.deduplication import DeduplicationItem, find_duplicate_groups
from mirsad_api.domains.query import classify_query, process_query
from mirsad_api.domains.ranking import calculate_score, is_candidate_match, relevance_score
from mirsad_api.domains.retrieval_metrics import aggregate_metrics, ranking_metrics
from mirsad_api.domains.semantic import LocalSemanticRanker, SemanticDocument

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "reports/relevance-recovery-holdout.json"
BASELINE_PATH = ROOT / "reports/holdout-error-analysis.json"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION = "fastembed-mean-pooling-v1"
SEMANTIC_WEIGHT = 0.75
QUALITY_BUDGET = 0.01
CANDIDATE_LIMIT = 20


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slices(judgment: dict[str, Any]) -> set[str]:
    values = set(judgment["slices"])
    if judgment["exact_phrase"]:
        values.add("exact")
    if "organization" in values:
        values.add("entity")
    if "ambiguous" not in values and "organization" not in values and not judgment["exact_phrase"]:
        values.add("topic")
    if "hard" in values:
        values.add("hard_collision")
    return values


def _duplicate_representatives(
    documents: list[dict[str, Any]],
    evaluation_now: datetime,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    numeric = {index: document for index, document in enumerate(documents, 1)}
    groups = find_duplicate_groups(
        [
            DeduplicationItem(
                key=index,
                source=document["source"],
                canonical_url=document["url"],
                title=document["title"],
                text=document["text"],
                published_at=evaluation_now - timedelta(hours=document["age_hours"]),
            )
            for index, document in numeric.items()
        ]
    )
    representative_by_id: dict[str, str] = {}
    evidence: list[dict[str, Any]] = []
    for group in groups:
        canonical = max(
            group.members,
            key=lambda key: (
                evaluation_now - timedelta(hours=numeric[key]["age_hours"]),
                numeric[key]["id"],
            ),
        )
        representative = numeric[canonical]["id"]
        member_ids = [numeric[key]["id"] for key in group.members]
        for identifier in member_ids:
            representative_by_id[identifier] = representative
        evidence.append(
            {
                "representative": representative,
                "members": sorted(member_ids),
                "stages": {numeric[key]["id"]: group.stages[key] for key in group.members},
            }
        )
    return representative_by_id, evidence


def _aggregate_cases(cases: list[dict[str, Any]], field: str) -> dict[str, float | int]:
    return aggregate_metrics(case[field] for case in cases)


def evaluate() -> dict[str, Any]:
    hashes = verify_frozen_holdout()
    corpus = _load(CORPUS_PATH)
    judgments = _load(JUDGMENTS_PATH)["queries"]
    documents = corpus["documents"]
    evaluation_now = datetime.fromisoformat(
        corpus["evaluation_now"].replace("Z", "+00:00")
    ).astimezone(UTC)
    representative_by_id, duplicate_groups = _duplicate_representatives(documents, evaluation_now)
    fts, row_ids = _fts_connection(documents)
    ranker = LocalSemanticRanker(
        enabled=True,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        cache_dir=str(ROOT / "data/models"),
        local_files_only=True,
        threads=4,
    )
    capability = ranker.capability_state()
    if capability[0] not in {"available", "ready"}:
        raise RuntimeError(f"Final semantic holdout cannot run: {capability[1]}")

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    cases: list[dict[str, Any]] = []
    component_samples: dict[str, list[float]] = defaultdict(list)
    ranking_samples: list[float] = []
    semantic_samples: list[float] = []
    total_started = time.perf_counter()
    for judgment in judgments:
        query_started = time.perf_counter()
        query = process_query(judgment["query"], exact_phrase=judgment["exact_phrase"])
        _strengths, normalized_bm25 = _fts_scores(fts, row_ids, query)
        candidates = [
            document
            for document in documents
            if is_candidate_match(
                query,
                document["title"],
                document["text"],
                canonical_url=document["url"],
            )
        ]
        candidates.sort(
            key=lambda document: (
                *relevance_score(
                    query,
                    document["title"],
                    document["text"],
                    bm25_normalized=normalized_bm25.get(document["id"], 0),
                    canonical_url=document["url"],
                )[:1],
                normalized_bm25.get(document["id"], 0),
                document["id"],
            ),
            reverse=True,
        )
        semantic_candidates = candidates[:CANDIDATE_LIMIT]
        key_to_id = {index: document["id"] for index, document in enumerate(semantic_candidates, 1)}
        semantic = ranker.score(
            query,
            [
                SemanticDocument(key=index, title=document["title"], text=document["text"])
                for index, document in enumerate(semantic_candidates, 1)
            ],
        )
        if semantic.state not in {"ready", "lexical_only"}:
            raise RuntimeError(
                f"Semantic evaluation failed for {judgment['id']}: {semantic.detail}"
            )
        semantic_samples.append(semantic.duration_ms)
        semantic_by_id = {key_to_id[key]: value for key, value in semantic.scores.items()}
        similarity_by_id = {key_to_id[key]: value for key, value in semantic.similarities.items()}
        scored: list[dict[str, Any]] = []
        relevant = set(judgment["relevant"])
        for document in candidates:
            identifier = document["id"]
            score = calculate_score(
                query=query,
                title=document["title"],
                text=document["text"],
                canonical_url=document["url"],
                published_at=evaluation_now - timedelta(hours=document["age_hours"]),
                engagement=document["engagement"],
                source_confidence=document["source_confidence"],
                cross_source_presence=document["cross_source_presence"],
                novelty=document["novelty"],
                bm25_normalized=normalized_bm25.get(identifier, 0),
                semantic_relevance=semantic_by_id.get(identifier),
                semantic_similarity=similarity_by_id.get(identifier),
                semantic_weight=SEMANTIC_WEIGHT,
                semantic_quality_budget=QUALITY_BUDGET,
                weights=DEFAULT_WEIGHTS,
                now=evaluation_now,
            )
            representative = representative_by_id.get(identifier, identifier) == identifier
            scored.append(
                {
                    "id": identifier,
                    "relevant": identifier in relevant,
                    "representative": representative,
                    "published": (
                        evaluation_now - timedelta(hours=document["age_hours"])
                    ).timestamp(),
                    "final_score": score.final_score,
                    "relevance": score.relevance,
                    "lexical_relevance": score.lexical_relevance,
                    "semantic_relevance": score.semantic_relevance,
                    "semantic_similarity": score.semantic_similarity,
                    "freshness": score.freshness,
                    "engagement": score.engagement,
                    "source_confidence": score.source_confidence,
                    "cross_source_presence": score.cross_source_presence,
                    "novelty": score.novelty,
                    "spam_penalty": score.spam_penalty,
                    "features": score.relevance_features,
                }
            )
            for field in (
                "final_score",
                "relevance",
                "lexical_relevance",
                "semantic_relevance",
                "freshness",
                "engagement",
                "source_confidence",
                "cross_source_presence",
                "novelty",
                "spam_penalty",
            ):
                value = getattr(score, field)
                if value is not None:
                    component_samples[field].append(float(value))
        raw = sorted(
            scored,
            key=lambda row: (
                row["final_score"],
                row["relevance"],
                row["published"],
                row["id"],
            ),
            reverse=True,
        )
        user_facing = sorted(
            scored,
            key=lambda row: (
                row["representative"],
                row["final_score"],
                row["lexical_relevance"],
                row["published"],
                row["id"],
            ),
            reverse=True,
        )
        unique = [row for row in user_facing if row["representative"]]
        unique_relevant = {
            representative_by_id.get(identifier, identifier) for identifier in relevant
        }
        raw_metrics = ranking_metrics([row["id"] for row in raw], relevant)
        unique_metrics = ranking_metrics([row["id"] for row in unique], unique_relevant)
        ranking_samples.append((time.perf_counter() - query_started) * 1000)
        cases.append(
            {
                "id": judgment["id"],
                "query": judgment["query"],
                "language": judgment["language"],
                "query_type": classify_query(query),
                "slices": sorted(_slices(judgment)),
                "candidate_count": len(candidates),
                "relevant": sorted(relevant),
                "raw_metrics": raw_metrics,
                "unique_metrics": unique_metrics,
                "top_15": raw[:15],
                "unique_top_10": [row["id"] for row in unique[:10]],
            }
        )
    total_ms = (time.perf_counter() - total_started) * 1000
    fts.close()

    languages = {
        language: _aggregate_cases(
            [case for case in cases if case["language"] == language], "unique_metrics"
        )
        for language in ("arabic", "english", "mixed")
    }
    slice_names = sorted({name for case in cases for name in case["slices"]})
    return {
        "schema": "mirsad.relevance-recovery-holdout",
        "version": "1.0",
        "frozen_hashes": hashes,
        "documents": len(documents),
        "queries": len(cases),
        "selected_strategy": {
            "candidate_retrieval": "intent-aware lexical candidates with SQLite FTS5 BM25",
            "candidate_limit": CANDIDATE_LIMIT,
            "semantic_model": MODEL_NAME,
            "semantic_model_version": MODEL_VERSION,
            "lexical_weight": 1 - SEMANTIC_WEIGHT,
            "semantic_weight": SEMANTIC_WEIGHT,
            "secondary_quality_budget": QUALITY_BUDGET,
            "duplicate_presentation": "representatives before duplicate copies",
        },
        "baseline": _load(BASELINE_PATH)["overall"],
        "raw_record_metrics": _aggregate_cases(cases, "raw_metrics"),
        "overall": _aggregate_cases(cases, "unique_metrics"),
        "language_metrics": languages,
        "slice_metrics": {
            name: _aggregate_cases(
                [case for case in cases if name in case["slices"]], "unique_metrics"
            )
            for name in slice_names
        },
        "component_means": {
            field: round(mean(values), 4) for field, values in component_samples.items()
        },
        "duplicate_groups": duplicate_groups,
        "performance": {
            "model_capability_before_run": capability[0],
            "total_evaluation_ms": round(total_ms, 2),
            "mean_query_pipeline_ms": round(mean(ranking_samples), 2),
            "mean_semantic_rerank_ms": round(mean(semantic_samples), 2),
            "first_semantic_rerank_ms": round(semantic_samples[0], 2),
            "warm_semantic_rerank_mean_ms": round(mean(semantic_samples[1:]), 2),
            "peak_rss_delta_kib": max(
                0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - rss_before
            ),
        },
        "cases": cases,
    }


def main() -> None:
    result = evaluate()
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "overall": result["overall"],
                "raw_record_metrics": result["raw_record_metrics"],
                "language_metrics": result["language_metrics"],
                "performance": result["performance"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
