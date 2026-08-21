from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
import tracemalloc
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from mirsad_api.domains.query import (
    ProcessedQuery,
    detect_language,
    fts_query,
    normalize_text,
    process_query,
    token_sequence,
    tokenize,
)
from mirsad_api.domains.ranking import calculate_score, is_candidate_match
from mirsad_api.domains.retrieval_metrics import aggregate_metrics, ranking_metrics

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "apps/api/tests/fixtures/blinded_holdout_documents.json"
JUDGMENTS_PATH = ROOT / "apps/api/tests/fixtures/blinded_holdout_judgments.json"
EXPECTED_HASHES = {
    CORPUS_PATH: "321f8f149552cdc8e8e0f6e07dca92972c86650d3ad4dc91e611aca5ba5123ee",
    JUDGMENTS_PATH: "c003fca383cf3bd9fb7e0f8bf5ec0eedf748d69fd144b1b803ce5447e2e9db29",
}
DEFAULT_WEIGHTS = {
    "relevance": 0.35,
    "freshness": 0.20,
    "engagement": 0.15,
    "source_confidence": 0.10,
    "cross_source_presence": 0.10,
    "novelty": 0.10,
}
POOL_SIZES = (20, 50, 100, 200)


def verify_frozen_holdout() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"Frozen holdout changed: {path.name} is {actual}, expected {expected}"
            )
        hashes[path.name] = actual
    return hashes


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains_sequence(content: tuple[str, ...], query: tuple[str, ...]) -> bool:
    if not content or not query or len(query) > len(content):
        return False
    width = len(query)
    return any(content[index : index + width] == query for index in range(len(content) - width + 1))


def _proximity(content: tuple[str, ...], query: tuple[str, ...]) -> float:
    required = set(query)
    if not content or not required or not required.issubset(content):
        return 0.0
    counts: dict[str, int] = {}
    left = 0
    best = len(content) + 1
    for right, token in enumerate(content):
        if token in required:
            counts[token] = counts.get(token, 0) + 1
        while len(counts) == len(required):
            best = min(best, right - left + 1)
            left_token = content[left]
            if left_token in counts:
                counts[left_token] -= 1
                if counts[left_token] == 0:
                    del counts[left_token]
            left += 1
    return min(1.0, len(required) / best) if best <= len(content) else 0.0


def _fts_connection(documents: list[dict[str, Any]]) -> tuple[sqlite3.Connection, dict[int, str]]:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE VIRTUAL TABLE holdout_fts USING fts5("
        "identifier UNINDEXED, title, text, normalized_title, normalized_text, "
        "tokenize='unicode61 remove_diacritics 2')"
    )
    ids: dict[int, str] = {}
    for row_id, document in enumerate(documents, 1):
        ids[row_id] = document["id"]
        connection.execute(
            "INSERT INTO holdout_fts("
            "rowid, identifier, title, text, normalized_title, normalized_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                row_id,
                document["id"],
                document["title"],
                document["text"],
                normalize_text(document["title"]),
                normalize_text(document["text"]),
            ),
        )
    return connection, ids


def _fts_scores(
    connection: sqlite3.Connection,
    ids: dict[int, str],
    query: ProcessedQuery,
) -> tuple[dict[str, float], dict[str, float]]:
    rows = connection.execute(
        "SELECT rowid, bm25(holdout_fts, 4.0, 1.0, 4.0, 1.0) "
        "FROM holdout_fts WHERE holdout_fts MATCH ?",
        (fts_query(query),),
    ).fetchall()
    strengths = {ids[int(row_id)]: max(0.0, -float(score)) for row_id, score in rows}
    maximum = max(strengths.values(), default=0.0)
    normalized = {
        identifier: round(100 * strength / maximum, 4) if maximum > 0 else 0.0
        for identifier, strength in strengths.items()
    }
    return strengths, normalized


def _term_rarity(
    query: ProcessedQuery,
    document_tokens: set[str],
    document_frequency: Counter[str],
    document_count: int,
) -> float:
    weights = {
        token: math.log((document_count + 1) / (document_frequency[token] + 1)) + 1
        for token in query.tokens
    }
    denominator = sum(weights.values()) or 1.0
    return (
        sum(weight for token, weight in weights.items() if token in document_tokens) / denominator
    )


def _language_compatibility(query: ProcessedQuery, document: dict[str, Any]) -> float:
    query_has_ar = any("\u0600" <= character <= "\u06ff" for character in query.normalized)
    query_has_latin = any("a" <= character <= "z" for character in query.normalized)
    content = f"{document['title']} {document['text']}"
    doc_has_ar = any("\u0600" <= character <= "\u06ff" for character in content)
    doc_has_latin = any(character.isascii() and character.isalpha() for character in content)
    if query_has_ar and query_has_latin:
        return 100.0 if doc_has_ar and doc_has_latin else 50.0
    return 100.0 if detect_language(content) == query.language else 50.0


def _feature_trace(
    query: ProcessedQuery,
    document: dict[str, Any],
    *,
    fts_strength: float,
    fts_normalized: float,
    document_frequency: Counter[str],
    document_count: int,
) -> dict[str, float]:
    title_sequence = token_sequence(document["title"])
    body_sequence = token_sequence(document["text"])
    combined_sequence = title_sequence + body_sequence
    title_tokens = set(title_sequence)
    body_tokens = set(body_sequence)
    combined_tokens = set(combined_sequence)
    query_tokens = set(query.tokens)
    denominator = max(1, len(query.tokens))
    return {
        "bm25_strength": round(fts_strength, 6),
        "bm25_normalized": round(fts_normalized, 2),
        "exact_full_query": float(_contains_sequence(combined_sequence, query.sequence)),
        "exact_phrase": float(_contains_sequence(body_sequence, query.sequence)),
        "title_exact_phrase": float(_contains_sequence(title_sequence, query.sequence)),
        "title_token_coverage": round(len(title_tokens & query_tokens) / denominator * 100, 2),
        "body_token_coverage": round(len(body_tokens & query_tokens) / denominator * 100, 2),
        "query_token_coverage": round(len(combined_tokens & query_tokens) / denominator * 100, 2),
        "token_proximity": round(_proximity(combined_sequence, query.tokens) * 100, 2),
        "term_rarity": round(
            _term_rarity(query, combined_tokens, document_frequency, document_count) * 100, 2
        ),
        "hashtag_match": 0.0,
        "handle_match": 0.0,
        "language_compatibility": _language_compatibility(query, document),
    }


def _metrics(ranked: list[str], relevant: set[str]) -> dict[str, object]:
    return ranking_metrics(ranked, relevant)


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, float | int]:
    return aggregate_metrics(case["metrics"] for case in cases)


def _failure_categories(case: dict[str, Any]) -> list[str]:
    if case["missing_relevant"]:
        return ["CANDIDATE_MISS"]
    ranks = case["metrics"]["relevant_ranks"]
    if ranks and max(ranks) <= 5:
        return []
    categories = ["RANKING_CALIBRATION"]
    if case["query_token_count"] == 1:
        categories.extend(("SHORT_QUERY_AMBIGUITY", "SEMANTIC_COLLISION"))
    else:
        categories.extend(("LEXICAL_COLLISION", "SEMANTIC_COLLISION"))
    if case["exact_phrase"]:
        categories.append("TITLE_FALSE_POSITIVE")
    relevant_rows = [row for row in case["trace"] if row["relevant"]]
    irrelevant_rows = [row for row in case["trace"] if not row["relevant"]]
    top_irrelevant = irrelevant_rows[:5]
    if relevant_rows and top_irrelevant:
        if mean(row["freshness"] for row in top_irrelevant) > mean(
            row["freshness"] for row in relevant_rows
        ):
            categories.append("FRESHNESS_INTERFERENCE")
        if mean(row["engagement"] for row in top_irrelevant) > mean(
            row["engagement"] for row in relevant_rows
        ):
            categories.append("ENGAGEMENT_INTERFERENCE")
    return list(dict.fromkeys(categories))


def analyze_holdout() -> dict[str, Any]:
    hashes = verify_frozen_holdout()
    corpus = _load_json(CORPUS_PATH)
    judgments = _load_json(JUDGMENTS_PATH)["queries"]
    documents = corpus["documents"]
    by_id = {document["id"]: document for document in documents}
    evaluation_now = datetime.fromisoformat(
        corpus["evaluation_now"].replace("Z", "+00:00")
    ).astimezone(UTC)
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(tokenize(f"{document['title']} {document['text']}")))
    connection, row_ids = _fts_connection(documents)
    cases: list[dict[str, Any]] = []
    relevant_total = 0
    relevant_in_candidates = 0
    relevant_below_5 = 0
    relevant_below_10 = 0

    for judgment in judgments:
        query = process_query(judgment["query"], exact_phrase=judgment["exact_phrase"])
        relevant = set(judgment["relevant"])
        relevant_total += len(relevant)
        fts_strengths, fts_normalized = _fts_scores(connection, row_ids, query)
        scored: list[dict[str, Any]] = []
        candidate_ids: set[str] = set()
        for document in documents:
            if not is_candidate_match(
                query, document["title"], document["text"], canonical_url=document["url"]
            ):
                continue
            candidate_ids.add(document["id"])
            content_tokens = set(tokenize(f"{document['title']} {document['text']}"))
            coverage = len(content_tokens & set(query.tokens)) / max(1, len(query.tokens))
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
                bm25_normalized=coverage * 100,
                weights=DEFAULT_WEIGHTS,
                now=evaluation_now,
            )
            scored.append(
                {
                    "id": document["id"],
                    "source": document["source"],
                    "title": document["title"],
                    "relevant": document["id"] in relevant,
                    **_feature_trace(
                        query,
                        document,
                        fts_strength=fts_strengths.get(document["id"], 0.0),
                        fts_normalized=fts_normalized.get(document["id"], 0.0),
                        document_frequency=document_frequency,
                        document_count=len(documents),
                    ),
                    "baseline_bm25_input": round(coverage * 100, 2),
                    "base_relevance": score.relevance,
                    "freshness": score.freshness,
                    "engagement": score.engagement,
                    "source_confidence": score.source_confidence,
                    "cross_source_presence": score.cross_source_presence,
                    "novelty": score.novelty,
                    "spam_penalty": score.spam_penalty,
                    "final_score": score.final_score,
                }
            )
        scored.sort(
            key=lambda row: (
                row["final_score"],
                -(evaluation_now - timedelta(hours=by_id[row["id"]]["age_hours"])).timestamp(),
                row["id"],
            ),
            reverse=True,
        )
        # Match the frozen evaluator's score, publication time, and identifier tie breaker.
        scored.sort(
            key=lambda row: (
                row["final_score"],
                (evaluation_now - timedelta(hours=by_id[row["id"]]["age_hours"])).timestamp(),
                row["id"],
            ),
            reverse=True,
        )
        ranked = [row["id"] for row in scored]
        metrics = _metrics(ranked, relevant)
        missing = sorted(relevant - candidate_ids)
        relevant_in_candidates += len(relevant & candidate_ids)
        relevant_below_5 += sum(rank > 5 for rank in metrics["relevant_ranks"])
        relevant_below_10 += sum(rank > 10 for rank in metrics["relevant_ranks"])
        case = {
            "id": judgment["id"],
            "query": judgment["query"],
            "exact_phrase": judgment["exact_phrase"],
            "language": judgment["language"],
            "slices": judgment["slices"],
            "query_intent": query.intent,
            "query_token_count": len(query.tokens),
            "expected_relevant": sorted(relevant),
            "candidate_count": len(candidate_ids),
            "candidate_recall": round(len(relevant & candidate_ids) / max(1, len(relevant)), 4),
            "missing_relevant": missing,
            "metrics": metrics,
            "trace": [{"rank": index, **row} for index, row in enumerate(scored[:15], 1)],
        }
        case["failure_categories"] = _failure_categories(case)
        cases.append(case)

    pool_results: list[dict[str, Any]] = []
    for pool_size in POOL_SIZES:
        tracemalloc.start()
        started = time.perf_counter()
        recalls: list[float] = []
        for case in cases:
            candidate_ids = [row["id"] for row in case["trace"][:pool_size]]
            relevant = set(case["expected_relevant"])
            recalls.append(len(set(candidate_ids) & relevant) / max(1, len(relevant)))
        elapsed = (time.perf_counter() - started) * 1000
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        pool_results.append(
            {
                "pool_size": pool_size,
                "candidate_recall": round(mean(recalls), 4),
                "latency_ms": round(elapsed, 4),
                "peak_memory_kib": round(peak / 1024, 2),
            }
        )

    result = {
        "schema": "mirsad.holdout-error-analysis",
        "version": "1.0",
        "frozen_hashes": hashes,
        "ranking_configuration": {
            "weights": DEFAULT_WEIGHTS,
            "freshness_half_life_hours": 48,
            "holdout_bm25_input": "query token coverage, retained to reproduce frozen baseline",
            "diagnostic_bm25": "SQLite FTS5 over title/text and normalized title/text",
        },
        "candidate_analysis": {
            "relevant_total": relevant_total,
            "relevant_in_candidates": relevant_in_candidates,
            "relevant_in_candidate_percentage": round(
                relevant_in_candidates / max(1, relevant_total), 4
            ),
            "relevant_below_top_5": relevant_below_5,
            "relevant_below_top_10": relevant_below_10,
            "retrieval_failures": relevant_total - relevant_in_candidates,
            "ranking_failures": sum(bool(case["failure_categories"]) for case in cases),
        },
        "overall": _aggregate(cases),
        "language_metrics": {
            language: _aggregate([case for case in cases if case["language"] == language])
            for language in ("arabic", "english", "mixed")
        },
        "pool_results": pool_results,
        "failure_category_counts": dict(
            Counter(category for case in cases for category in case["failure_categories"])
        ),
        "cases": cases,
    }
    connection.close()
    return result


def _metric_row(label: str, metrics: dict[str, Any]) -> str:
    return (
        f"| {label} | {metrics['queries']} | {metrics['p_at_5']:.4f} | "
        f"{metrics['p_at_10']:.4f} | {metrics['mrr']:.4f} | "
        f"{metrics['recall_at_10']:.4f} | {metrics['recall_at_20']:.4f} | "
        f"{metrics['ndcg_at_5']:.4f} | {metrics['ndcg_at_10']:.4f} | "
        f"{metrics['success_at_1']:.4f} | {metrics['success_at_3']:.4f} | "
        f"{metrics['success_at_5']:.4f} |"
    )


def write_reports(result: dict[str, Any]) -> None:
    report_dir = ROOT / "reports"
    (report_dir / "holdout-error-analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    candidate = result["candidate_analysis"]
    lines = [
        "# Holdout Error Analysis",
        "",
        "Generated before relevance-recovery algorithm changes. Frozen hashes were verified.",
        "",
        "## Retrieval Versus Ranking",
        "",
        f"- Judged relevant documents: {candidate['relevant_total']}",
        f"- Relevant documents entering the candidate set: {candidate['relevant_in_candidates']} "
        f"({candidate['relevant_in_candidate_percentage']:.2%})",
        f"- Candidate misses: {candidate['retrieval_failures']}",
        f"- Relevant documents below rank 5: {candidate['relevant_below_top_5']}",
        f"- Relevant documents below rank 10: {candidate['relevant_below_top_10']}",
        f"- Queries classified with ranking failures: {candidate['ranking_failures']}/16",
        "",
        "All judged documents enter the current candidate set; this holdout's primary defect is "
        "ranking under dense collisions, not retrieval recall.",
        "",
        "## Baseline Metrics",
        "",
        "| Segment | Queries | P@5 | P@10 | MRR | R@10 | R@20 | nDCG@5 | nDCG@10 "
        "| S@1 | S@3 | S@5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _metric_row("Arabic", result["language_metrics"]["arabic"]),
        _metric_row("English", result["language_metrics"]["english"]),
        _metric_row("Mixed", result["language_metrics"]["mixed"]),
        _metric_row("Overall", result["overall"]),
        "",
        "## Failure Categories",
        "",
        *(
            f"- `{name}`: {count} queries"
            for name, count in sorted(result["failure_category_counts"].items())
        ),
        "",
        "## Candidate Limits",
        "",
        "| Pool | Candidate recall | Evaluation latency | Peak traced memory |",
        "| ---: | ---: | ---: | ---: |",
        *(
            f"| {row['pool_size']} | {row['candidate_recall']:.4f} | {row['latency_ms']:.4f} ms | "
            f"{row['peak_memory_kib']:.2f} KiB |"
            for row in result["pool_results"]
        ),
        "",
        "Every query has only 12-13 candidates after intent-aware lexical admission, so pools from "
        "20 through 200 have identical recall. Increasing the production pool cannot repair these "
        "ordering failures.",
        "",
        "## Query Traces",
        "",
        "`BM25` is real in-memory SQLite FTS5 evidence. `Baseline BM25` is the legacy evaluator's "
        "coverage proxy retained solely to reproduce the frozen score.",
        "",
    ]
    for case in result["cases"]:
        lines.extend(
            [
                f"### {case['id']}: {case['query']}",
                "",
                f"- Expected relevant: {', '.join(case['expected_relevant'])}",
                f"- Relevant ranks: {case['metrics']['relevant_ranks']}",
                f"- Candidate recall: {case['candidate_recall']:.4f}",
                f"- Failure classification: {', '.join(case['failure_categories']) or 'none'}",
                "",
                "| Rank | ID | Rel | Source | BM25 | Baseline BM25 | Exact | Title phrase | "
                "Title cov. | Body cov. | Coverage | Proximity | Rarity | Language | Base rel. | "
                "Fresh | Engage | Confidence | Cross | Novelty | Penalty | Final | Title |",
                "| ---: | --- | :---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
                "---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
                "---: | --- |",
            ]
        )
        for row in case["trace"]:
            lines.append(
                f"| {row['rank']} | {row['id']} | {'Y' if row['relevant'] else ''} | "
                f"{row['source']} | {row['bm25_normalized']:.2f} | "
                f"{row['baseline_bm25_input']:.2f} | {row['exact_phrase']:.0f} | "
                f"{row['title_exact_phrase']:.0f} | {row['title_token_coverage']:.0f} | "
                f"{row['body_token_coverage']:.0f} | {row['query_token_coverage']:.0f} | "
                f"{row['token_proximity']:.0f} | {row['term_rarity']:.0f} | "
                f"{row['language_compatibility']:.0f} | {row['base_relevance']:.2f} | "
                f"{row['freshness']:.2f} | {row['engagement']:.2f} | "
                f"{row['source_confidence']:.2f} | {row['cross_source_presence']:.2f} | "
                f"{row['novelty']:.2f} | {row['spam_penalty']:.2f} | "
                f"{row['final_score']:.2f} | {row['title'].replace('|', '/')} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Root Cause",
            "",
            "Candidate recall is complete. The dominant failures are semantically different "
            "records that repeat the exact query phrase in both title and body, making coverage, "
            "phrase, proximity, rarity, and often FTS BM25 nearly indistinguishable. Relevance "
            "saturates at 100, so freshness and engagement order the collision set. This is a "
            "ranking and semantic disambiguation problem; larger candidate pools or simple "
            "query-token weights cannot solve it.",
        ]
    )
    (report_dir / "holdout-error-analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    result = analyze_holdout()
    write_reports(result)
    print(
        json.dumps(
            {
                "candidate_analysis": result["candidate_analysis"],
                "overall": result["overall"],
                "failure_category_counts": result["failure_category_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
