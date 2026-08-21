from __future__ import annotations

import argparse
import inspect
import json
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from mirsad_api.config import Settings
from mirsad_api.domains.clustering import build_cluster_candidate_plan, cluster_items
from mirsad_api.domains.deduplication import DeduplicationItem
from mirsad_api.domains.query import tokenize
from mirsad_api.domains.semantic import LocalSemanticRanker, SemanticDocument

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_PATH = ROOT / "apps/api/tests/fixtures/clustering_quality_documents.json"
JUDGMENTS_PATH = ROOT / "apps/api/tests/fixtures/clustering_quality_judgments.json"


def _load() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    documents_payload = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))
    judgments_payload = json.loads(JUDGMENTS_PATH.read_text(encoding="utf-8"))
    return (
        {document["id"]: document for document in documents_payload["documents"]},
        judgments_payload["cases"],
    )


def _expected_pairs(case: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        tuple(sorted((left, right)))
        for group in case["same_story_groups"]
        for index, left in enumerate(group)
        for right in group[index + 1 :]
    }


def _predicted_pairs(clusters: list[Any], key_to_id: dict[int, str]) -> set[tuple[str, str]]:
    return {
        tuple(sorted((key_to_id[left], key_to_id[right])))
        for cluster in clusters
        for index, left in enumerate(cluster.members)
        for right in cluster.members[index + 1 :]
    }


def _run_case(
    case: dict[str, Any],
    documents: dict[str, dict[str, Any]],
    semantic_ranker: LocalSemanticRanker | None,
) -> dict[str, Any]:
    key_to_id = {index: document_id for index, document_id in enumerate(case["document_ids"], 1)}
    items = [
        DeduplicationItem(
            key=key,
            source=documents[document_id]["source"],
            canonical_url=documents[document_id]["url"],
            title=documents[document_id]["title"],
            text=documents[document_id]["text"],
            published_at=datetime.fromisoformat(
                documents[document_id]["published_at"].replace("Z", "+00:00")
            ),
        )
        for key, document_id in key_to_id.items()
    ]
    kwargs: dict[str, Any] = {}
    if "query_tokens" in inspect.signature(cluster_items).parameters:
        kwargs["query_tokens"] = tokenize(case["query"])
    semantic_state = "not_requested"
    semantic_duration_ms = 0.0
    candidate_pairs = 0
    supports_candidate_plan = "candidate_plan" in inspect.signature(cluster_items).parameters
    if supports_candidate_plan:
        plan = build_cluster_candidate_plan(items, query_tokens=tokenize(case["query"]))
        kwargs["candidate_plan"] = plan
        candidate_pairs = len(plan.pairs)
    if semantic_ranker is not None and supports_candidate_plan:
        semantic_documents = [
            SemanticDocument(
                key=item.key,
                title=item.title,
                text=item.text,
            )
            for item in items
            if item.key in plan.representative_keys
        ]
        semantic = semantic_ranker.cluster_similarities(
            semantic_documents,
            plan.pairs,
        )
        kwargs.update(
            {
                "semantic_similarities": semantic.similarities,
            }
        )
        semantic_state = semantic.state
        semantic_duration_ms = semantic.duration_ms
    started = perf_counter()
    clusters = cluster_items(items, **kwargs)
    duration_ms = (perf_counter() - started) * 1000
    expected = _expected_pairs(case)
    predicted = _predicted_pairs(clusters, key_to_id)
    true_positive = expected & predicted
    false_positive = predicted - expected
    false_negative = expected - predicted
    cluster_views = [
        {
            **asdict(cluster),
            "members": [key_to_id[key] for key in cluster.members],
            "earliest_at": cluster.earliest_at.isoformat() if cluster.earliest_at else None,
            "latest_at": cluster.latest_at.isoformat() if cluster.latest_at else None,
        }
        for cluster in clusters
    ]
    return {
        "id": case["id"],
        "query": case["query"],
        "language": case["language"],
        "documents": len(items),
        "clusters": len(clusters),
        "largest_cluster": max(len(cluster.members) for cluster in clusters),
        "duration_ms": round(duration_ms, 3),
        "candidate_pairs": candidate_pairs,
        "semantic_state": semantic_state,
        "semantic_duration_ms": semantic_duration_ms,
        "true_positive_pairs": len(true_positive),
        "false_positive_pairs": len(false_positive),
        "false_negative_pairs": len(false_negative),
        "expected_positive_pairs": len(expected),
        "predicted_positive_pairs": len(predicted),
        "false_merges": [list(pair) for pair in sorted(false_positive)],
        "missed_merges": [list(pair) for pair in sorted(false_negative)],
        "cluster_assignments": cluster_views,
    }


def evaluate(label: str, *, use_semantic: bool = False) -> dict[str, Any]:
    documents, cases = _load()
    semantic_ranker = None
    if use_semantic:
        settings = Settings()
        cache_dir = Path(settings.semantic_model_cache_dir)
        if not cache_dir.is_absolute():
            cache_dir = ROOT / cache_dir
        semantic_ranker = LocalSemanticRanker(
            enabled=True,
            model_name=settings.semantic_model_name,
            model_version=settings.semantic_model_version,
            cache_dir=str(cache_dir),
            local_files_only=True,
            threads=settings.semantic_threads,
        )
    results = [_run_case(case, documents, semantic_ranker) for case in cases]
    true_positive = sum(case["true_positive_pairs"] for case in results)
    false_positive = sum(case["false_positive_pairs"] for case in results)
    false_negative = sum(case["false_negative_pairs"] for case in results)
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 1.0
    recall = true_positive / recall_denominator if recall_denominator else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "schema": "mirsad.clustering-evaluation",
        "version": "1.0",
        "label": label,
        "fixture_hashes": {
            DOCUMENTS_PATH.name: sha256(DOCUMENTS_PATH.read_bytes()).hexdigest(),
            JUDGMENTS_PATH.name: sha256(JUDGMENTS_PATH.read_bytes()).hexdigest(),
        },
        "summary": {
            "cases": len(results),
            "documents": sum(case["documents"] for case in results),
            "expected_positive_pairs": true_positive + false_negative,
            "predicted_positive_pairs": true_positive + false_positive,
            "true_positive_pairs": true_positive,
            "false_merges": false_positive,
            "missed_merges": false_negative,
            "pairwise_precision": round(precision, 4),
            "pairwise_recall": round(recall, 4),
            "pairwise_f1": round(f1, 4),
            "total_duration_ms": round(sum(case["duration_ms"] for case in results), 3),
            "semantic_duration_ms": round(
                sum(case["semantic_duration_ms"] for case in results), 3
            ),
            "candidate_pairs": sum(case["candidate_pairs"] for case in results),
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic story clustering")
    parser.add_argument("--label", default="current")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--semantic", action="store_true")
    args = parser.parse_args()
    payload = evaluate(args.label, use_semantic=args.semantic)
    output = args.output or ROOT / f"reports/clustering-evaluation-{args.label}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
