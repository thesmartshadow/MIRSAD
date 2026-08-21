from __future__ import annotations

import argparse
import hashlib
import json
import resource
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

import numpy as np
from fastembed import TextEmbedding

from mirsad_api.domains.retrieval_metrics import aggregate_metrics, ranking_metrics

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "development": ROOT / "apps/api/tests/fixtures/mafer_phase3_development.json",
    "holdout": ROOT / "apps/api/tests/fixtures/mafer_phase3_holdout.json",
}
EXPECTED_HOLDOUT_SHA256 = "50b06e990e39e41995893b4de288553d16d4f575ca2d825554039004b23b5ca2"
MODELS = {
    "minilm": {
        "name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "license": "Apache-2.0",
        "declared_size_gib": 0.22,
    },
    "mpnet": {
        "name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "license": "Apache-2.0",
        "declared_size_gib": 1.0,
    },
}


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def evaluate(split: str, model_key: str) -> dict[str, Any]:
    fixture = FIXTURES[split]
    fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if split == "holdout" and fixture_hash != EXPECTED_HOLDOUT_SHA256:
        raise RuntimeError("Frozen Phase-3 holdout hash mismatch")
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
    documents: list[dict[str, str]] = []
    relevant_by_case: dict[str, set[str]] = {}
    for case in cases:
        relevant_by_case[case["id"]] = set()
        for index, text in enumerate(case["semantic_positive"], 1):
            identifier = f"{case['id']}:positive:{index}"
            documents.append({"id": identifier, "text": text})
            relevant_by_case[case["id"]].add(identifier)
        for index, text in enumerate(case["semantic_negative"], 1):
            documents.append({"id": f"{case['id']}:negative:{index}", "text": text})

    definition = MODELS[model_key]
    cache_dir = ROOT / "data/models"
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    init_started = perf_counter()
    model = TextEmbedding(model_name=definition["name"], cache_dir=str(cache_dir), threads=4)
    initialization_ms = (perf_counter() - init_started) * 1_000
    encode_started = perf_counter()
    vectors = list(model.embed([document["text"] for document in documents], batch_size=32))
    document_encoding_ms = (perf_counter() - encode_started) * 1_000
    document_vectors = {
        document["id"]: np.asarray(vector, dtype=np.float32)
        for document, vector in zip(documents, vectors, strict=True)
    }
    query_times: list[float] = []
    rerank_times: list[float] = []
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        query_started = perf_counter()
        query_vector = np.asarray(next(model.query_embed(case["query"])), dtype=np.float32)
        query_times.append((perf_counter() - query_started) * 1_000)
        ranking_started = perf_counter()
        scores = {
            document["id"]: _cosine(query_vector, document_vectors[document["id"]])
            for document in documents
        }
        ranked = sorted(scores, key=lambda identifier: (-scores[identifier], identifier))
        rerank_times.append((perf_counter() - ranking_started) * 1_000)
        evaluated.append(
            {
                "id": case["id"],
                "query": case["query"],
                "language": case["language"],
                "class": case["class"],
                "metrics": ranking_metrics(ranked, relevant_by_case[case["id"]]),
                "relevant_ranks": [
                    ranked.index(identifier) + 1
                    for identifier in sorted(relevant_by_case[case["id"]])
                ],
                "top_10": ranked[:10],
            }
        )
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    def aggregate(values: list[dict[str, Any]]) -> dict[str, Any]:
        return aggregate_metrics(value["metrics"] for value in values)

    result = {
        "schema": "mirsad.mafer-phase3-model-shadow",
        "version": "1.0",
        "split": split,
        "fixture_sha256": fixture_hash,
        "model": definition,
        "documents": len(documents),
        "queries": len(cases),
        "metrics": {
            "overall": aggregate(evaluated),
            "language": {
                language: aggregate([value for value in evaluated if value["language"] == language])
                for language in sorted({value["language"] for value in evaluated})
            },
            "class": {
                query_class: aggregate(
                    [value for value in evaluated if value["class"] == query_class]
                )
                for query_class in sorted({value["class"] for value in evaluated})
            },
        },
        "performance": {
            "initialization_ms": round(initialization_ms, 2),
            "document_encoding_ms": round(document_encoding_ms, 2),
            "document_encoding_per_item_ms": round(
                document_encoding_ms / max(1, len(documents)), 4
            ),
            "query_encoding_mean_ms": round(mean(query_times), 4),
            "reranking_mean_ms": round(mean(rerank_times), 4),
            "peak_rss_delta_kib": max(0, rss_after - rss_before),
        },
        "cases": evaluated,
    }
    output = ROOT / f"reports/mafer-phase3-model-{model_key}-{split}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=sorted(FIXTURES), required=True)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    args = parser.parse_args()
    result = evaluate(args.split, args.model)
    print(
        json.dumps(
            {
                "split": result["split"],
                "model": result["model"],
                "metrics": result["metrics"],
                "performance": result["performance"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
