from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mirsad_api.config import Settings
from mirsad_api.domains.query import process_query
from mirsad_api.domains.ranking import calculate_score
from mirsad_api.domains.semantic import (
    LocalSemanticRanker,
    SemanticDocument,
    SemanticPreparationStats,
    build_semantic_ranker,
    score_in_worker,
)
from mirsad_api.services.semantic_preparation import SemanticPreparationCoordinator


class FakeEmbeddingModel:
    def __init__(self) -> None:
        self.document_batches = 0

    def query_embed(self, _query: str):
        yield [1.0, 0.0]

    def embed(self, documents: list[str], *, batch_size: int):
        assert batch_size == len(documents)
        self.document_batches += 1
        for document in documents:
            yield [1.0, 0.0] if "relevant" in document else [0.0, 1.0]


def test_local_semantic_ranker_caches_documents_by_content_and_model_version() -> None:
    model = FakeEmbeddingModel()
    ranker = LocalSemanticRanker(enabled=True, model_version="fixture-v1")
    ranker._model = model
    documents = [
        SemanticDocument(key=1, title="Arabic relevant", text="وزارة التخطيط relevant"),
        SemanticDocument(key=2, title="Collision", text="وزارة التخطيط unrelated"),
    ]

    first = ranker.score(process_query("وزارة التخطيط"), documents)
    second = ranker.score(process_query("وزارة التخطيط"), documents)

    assert first.state == "ready"
    assert first.cache_misses == 2
    assert second.cache_hits == 2
    assert second.cache_misses == 0
    assert first.scores[1] > first.scores[2]
    assert first.scores == second.scores
    assert first.similarities == second.similarities
    assert first.timings_ms["candidate_embedding_generation"] >= 0
    assert second.timings_ms["candidate_embedding_generation"] == 0
    assert first.batch_size == 2
    assert second.batch_size == 0
    assert model.document_batches == 1


def test_semantic_embedding_batches_are_bounded_and_versioned() -> None:
    class BatchModel(FakeEmbeddingModel):
        def embed(self, documents: list[str], *, batch_size: int):
            assert batch_size == 32
            self.document_batches += 1
            for _document in documents:
                yield [1.0, 0.0]

    documents = [
        SemanticDocument(key=index, title=f"Record {index}", text="public policy relevant")
        for index in range(50)
    ]
    model = BatchModel()
    ranker = LocalSemanticRanker(enabled=True, model_version="fixture-v1")
    ranker._model = model
    result = ranker.score(process_query("public policy"), documents)
    alternate = LocalSemanticRanker(enabled=True, model_version="fixture-v2")

    assert result.batch_size == 32
    assert result.cache_misses == 50
    assert ranker._content_key(documents[0]) != alternate._content_key(documents[0])


def test_exact_social_identifiers_remain_lexical_only() -> None:
    ranker = LocalSemanticRanker(enabled=True)

    result = ranker.score(
        process_query("#Baghdad"),
        [SemanticDocument(key=1, title="#Baghdad", text="Public update")],
    )

    assert result.state == "lexical_only"
    assert result.query_type == "HASHTAG"
    assert result.scores == {}


def test_missing_semantic_model_falls_back_without_repeated_loading(monkeypatch) -> None:
    ranker = LocalSemanticRanker(enabled=True)
    attempts = 0

    def fail_load():
        nonlocal attempts
        attempts += 1
        raise FileNotFoundError("secret local path must not escape")

    monkeypatch.setattr(ranker, "_load_model", fail_load)
    documents = [SemanticDocument(key=1, title="Public policy", text="Detailed report")]

    first = ranker.score(process_query("public policy"), documents)
    second = ranker.score(process_query("public policy"), documents)

    assert first.state == second.state == "unavailable"
    assert first.scores == second.scores == {}
    assert "secret" not in (first.detail or "")
    assert attempts == 1


@pytest.mark.asyncio
async def test_semantic_worker_supports_repeated_calls_without_default_executor() -> None:
    model = FakeEmbeddingModel()
    ranker = LocalSemanticRanker(enabled=True)
    ranker._model = model
    query = process_query("public policy")
    documents = [SemanticDocument(key=1, title="Policy relevant", text="Public policy relevant")]

    first = await score_in_worker(ranker, query, documents)
    second = await score_in_worker(ranker, query, documents)

    assert first.state == second.state == "ready"
    assert second.cache_hits == 1


def test_relative_semantic_cache_is_resolved_from_repository_root() -> None:
    ranker = build_semantic_ranker(
        Settings(semantic_model_cache_dir="data/models", semantic_ranking_enabled=False)
    )

    assert ranker.cache_dir.is_absolute()
    assert ranker.cache_dir.as_posix().endswith("/MIRSAD/data/models")


@pytest.mark.asyncio
async def test_semantic_preparation_is_bounded_deduplicated_and_cleans_up() -> None:
    model = FakeEmbeddingModel()
    ranker = LocalSemanticRanker(enabled=True)
    ranker._model = model
    coordinator = SemanticPreparationCoordinator(ranker, max_candidates=20)
    repeated = SemanticDocument(key=999, title="Record 0", text="public relevant")
    documents = [
        SemanticDocument(key=index, title=f"Record {index}", text="public relevant")
        for index in range(25)
    ]

    accepted = await coordinator.submit([*documents, repeated])
    summary = await coordinator.finish(collection_started=0.0, collection_finished=0.0)

    assert accepted == 20
    assert summary.eligible_candidates == 20
    assert summary.completed_candidates == 20
    assert summary.cache_misses == 20
    assert coordinator.queued == 0
    assert coordinator.worker_count == 0
    assert model.document_batches == 1


@pytest.mark.asyncio
async def test_prepared_and_unprepared_semantic_scores_and_order_are_identical() -> None:
    documents = [
        SemanticDocument(
            key=index,
            title=f"Record {index}",
            text="relevant evidence" if index % 2 == 0 else "unrelated record",
        )
        for index in range(20)
    ]
    query = process_query("relevant evidence")
    baseline = LocalSemanticRanker(enabled=True)
    baseline._model = FakeEmbeddingModel()
    prepared = LocalSemanticRanker(enabled=True)
    prepared._model = FakeEmbeddingModel()
    baseline_scores = baseline.score(query, documents)
    coordinator = SemanticPreparationCoordinator(prepared, max_candidates=20)
    await coordinator.submit(documents)
    summary = await coordinator.finish(collection_started=0.0, collection_finished=0.0)
    prepared_scores = prepared.score(query, documents)

    assert summary.cache_misses == 20
    assert prepared_scores.cache_hits == 20
    assert prepared_scores.scores == baseline_scores.scores
    assert prepared_scores.similarities == baseline_scores.similarities
    assert sorted(prepared_scores.scores, key=prepared_scores.scores.get, reverse=True) == sorted(
        baseline_scores.scores, key=baseline_scores.scores.get, reverse=True
    )
    weights = {
        "relevance": 0.35,
        "freshness": 0.20,
        "engagement": 0.15,
        "source_confidence": 0.10,
        "cross_source_presence": 0.10,
        "novelty": 0.10,
    }
    now = datetime(2026, 8, 21, tzinfo=UTC)

    def final_scores(semantic_scores):
        return {
            document.key: calculate_score(
                query=query,
                title=document.title,
                text=document.text,
                canonical_url=f"https://example.com/{document.key}",
                published_at=now,
                engagement=20,
                source_confidence=60,
                semantic_relevance=semantic_scores.scores[document.key],
                semantic_similarity=semantic_scores.similarities[document.key],
                semantic_weight=0.75,
                semantic_quality_budget=0.01,
                weights=weights,
                now=now,
            ).final_score
            for document in documents
        }

    baseline_final = final_scores(baseline_scores)
    prepared_final = final_scores(prepared_scores)
    assert prepared_final == baseline_final
    assert sorted(prepared_final, key=prepared_final.get, reverse=True) == sorted(
        baseline_final, key=baseline_final.get, reverse=True
    )


@pytest.mark.asyncio
async def test_precompute_failure_is_nonfatal_and_search_a_b_metrics_are_isolated() -> None:
    class FailOnceRanker(LocalSemanticRanker):
        def __init__(self) -> None:
            super().__init__(enabled=True)
            self._model = FakeEmbeddingModel()
            self.fail = True

        def prepare(self, documents: list[SemanticDocument]) -> SemanticPreparationStats:
            if self.fail:
                self.fail = False
                return SemanticPreparationStats("failed", 1.0, detail="fixture failure")
            return super().prepare(documents)

    ranker = FailOnceRanker()
    first = SemanticPreparationCoordinator(ranker, max_candidates=20)
    second = SemanticPreparationCoordinator(ranker, max_candidates=20)
    document_a = SemanticDocument(key=1, title="A", text="relevant A")
    document_b = SemanticDocument(key=2, title="B", text="relevant B")
    await first.submit([document_a])
    first_summary = await first.finish(collection_started=0.0, collection_finished=0.0)
    await second.submit([document_b])
    second_summary = await second.finish(collection_started=0.0, collection_finished=0.0)
    result = ranker.score(process_query("relevant"), [document_a, document_b])

    assert first_summary.failed is True
    assert first_summary.completed_candidates == 0
    assert second_summary.failed is False
    assert second_summary.completed_candidates == 1
    assert result.state == "ready"
    assert set(result.scores) == {1, 2}
