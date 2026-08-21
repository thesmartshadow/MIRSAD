from __future__ import annotations

import pytest

from mirsad_api.config import Settings
from mirsad_api.domains.query import process_query
from mirsad_api.domains.semantic import (
    LocalSemanticRanker,
    SemanticDocument,
    build_semantic_ranker,
    score_in_worker,
)


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
