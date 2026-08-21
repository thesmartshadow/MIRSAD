from __future__ import annotations

import asyncio
import hashlib
import math
import warnings
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Protocol

from .query import ProcessedQuery, classify_query, normalize_text

DEFAULT_SEMANTIC_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SEMANTIC_MODEL_VERSION = "fastembed-mean-pooling-v1"
LEXICAL_ONLY_QUERY_TYPES = {"HASHTAG", "HANDLE", "URL"}
_SEMANTIC_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mirsad-semantic")


@dataclass(frozen=True, slots=True)
class SemanticDocument:
    key: int
    title: str | None
    text: str


@dataclass(frozen=True, slots=True)
class SemanticScores:
    scores: dict[int, float]
    similarities: dict[int, float]
    state: str
    model: str | None
    model_version: str | None
    query_type: str
    duration_ms: float
    cache_hits: int = 0
    cache_misses: int = 0
    timings_ms: dict[str, float] = field(default_factory=dict)
    batch_size: int = 0
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ClusterSemanticScores:
    similarities: dict[tuple[int, int], float]
    state: str
    model: str | None
    model_version: str | None
    duration_ms: float
    candidate_pairs: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    timings_ms: dict[str, float] = field(default_factory=dict)
    batch_size: int = 0
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingBatchStats:
    cache_lookup_ms: float
    generation_ms: float
    batch_size: int


class SemanticRanker(Protocol):
    def score(
        self,
        query: ProcessedQuery,
        documents: list[SemanticDocument],
    ) -> SemanticScores: ...


async def score_in_worker(
    ranker: SemanticRanker,
    query: ProcessedQuery,
    documents: list[SemanticDocument],
) -> SemanticScores:
    """Run bounded model work outside the event loop without its default executor."""

    future = _SEMANTIC_EXECUTOR.submit(ranker.score, query, documents)
    while not future.done():
        await asyncio.sleep(0.002)
    return future.result()


async def cluster_score_in_worker(
    ranker: SemanticRanker,
    documents: list[SemanticDocument],
    pairs: tuple[tuple[int, int], ...],
) -> ClusterSemanticScores:
    method = getattr(ranker, "cluster_similarities", None)
    if not callable(method):
        return ClusterSemanticScores(
            similarities={},
            state="unsupported",
            model=None,
            model_version=None,
            duration_ms=0.0,
            candidate_pairs=len(pairs),
            detail="Semantic ranker does not expose clustering similarities",
        )
    future = _SEMANTIC_EXECUTOR.submit(method, documents, pairs)
    while not future.done():
        await asyncio.sleep(0.002)
    return future.result()


class LocalSemanticRanker:
    """Optional local ONNX sentence reranker with bounded in-process embedding cache."""

    def __init__(
        self,
        *,
        enabled: bool,
        model_name: str = DEFAULT_SEMANTIC_MODEL,
        model_version: str = DEFAULT_SEMANTIC_MODEL_VERSION,
        cache_dir: str = "data/models",
        local_files_only: bool = True,
        threads: int = 4,
        embedding_cache_size: int = 5000,
    ) -> None:
        self.enabled = enabled
        self.model_name = model_name
        self.model_version = model_version
        self.cache_dir = Path(cache_dir)
        self.local_files_only = local_files_only
        self.threads = threads
        self.embedding_cache_size = embedding_cache_size
        self._model: Any | None = None
        self._model_error: str | None = None
        self._embeddings: OrderedDict[str, Any] = OrderedDict()
        self._lock = Lock()
        self._model_lock = Lock()

    def capability_state(self) -> tuple[str, str]:
        if not self.enabled:
            return "disabled", "Local semantic reranking is disabled"
        if self._model_error:
            return "unavailable", self._model_error
        if self._model is not None:
            return "ready", f"{self.model_name} loaded locally"
        try:
            import fastembed  # noqa: F401
        except ImportError:
            return "unavailable", "Optional fastembed dependency is not installed"
        model_files = tuple(self.cache_dir.rglob("model_optimized.onnx"))
        if not model_files:
            return "unavailable", "Local semantic model is not installed"
        return "available", f"{self.model_name} is installed and will load on demand"

    def score(
        self,
        query: ProcessedQuery,
        documents: list[SemanticDocument],
    ) -> SemanticScores:
        started = perf_counter()
        query_type = classify_query(query)
        if not self.enabled:
            return self._empty("disabled", query_type, started, "Semantic reranking is disabled")
        if query_type in LEXICAL_ONLY_QUERY_TYPES:
            return self._empty(
                "lexical_only",
                query_type,
                started,
                "Exact hashtag, handle, and URL intent remains lexical",
            )
        if not documents:
            return self._empty("empty", query_type, started)
        if self._model_error:
            return self._empty("unavailable", query_type, started, self._model_error)
        try:
            model_started = perf_counter()
            model = self._load_model()
            model_load_ms = (perf_counter() - model_started) * 1000
            query_started = perf_counter()
            query_vector = next(model.query_embed(query.original))
            query_encoding_ms = (perf_counter() - query_started) * 1000
            vectors, cache_hits, cache_misses, batch_stats = self._document_vectors(
                model, documents
            )
            similarity_started = perf_counter()
            similarities = {
                document.key: round(self._cosine(query_vector, vectors[document.key]), 6)
                for document in documents
            }
            scores = {
                key: round(max(0.0, min(100.0, (similarity + 1) * 50)), 2)
                for key, similarity in similarities.items()
            }
            similarity_ms = (perf_counter() - similarity_started) * 1000
            return SemanticScores(
                scores=scores,
                similarities=similarities,
                state="ready",
                model=self.model_name,
                model_version=self.model_version,
                query_type=query_type,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                timings_ms={
                    "model_load": round(model_load_ms, 2),
                    "query_encoding": round(query_encoding_ms, 2),
                    "candidate_cache_lookup": batch_stats.cache_lookup_ms,
                    "candidate_embedding_generation": batch_stats.generation_ms,
                    "similarity": round(similarity_ms, 2),
                },
                batch_size=batch_stats.batch_size,
            )
        except Exception as error:
            self._model_error = self._safe_error(error)
            return self._empty("unavailable", query_type, started, self._model_error)

    def cluster_similarities(
        self,
        documents: list[SemanticDocument],
        pairs: tuple[tuple[int, int], ...],
    ) -> ClusterSemanticScores:
        started = perf_counter()
        if not self.enabled:
            return self._empty_cluster(
                "disabled", started, pairs, "Semantic reranking is disabled"
            )
        if not documents or not pairs:
            return self._empty_cluster("empty", started, pairs)
        if self._model_error:
            return self._empty_cluster("unavailable", started, pairs, self._model_error)
        try:
            model_started = perf_counter()
            model = self._load_model()
            model_load_ms = (perf_counter() - model_started) * 1000
            required_keys = {key for pair in pairs for key in pair}
            selected = [document for document in documents if document.key in required_keys]
            vectors, cache_hits, cache_misses, batch_stats = self._document_vectors(
                model, selected
            )
            similarity_started = perf_counter()
            similarities = {
                pair: round(self._cosine(vectors[pair[0]], vectors[pair[1]]), 6)
                for pair in pairs
                if pair[0] in vectors and pair[1] in vectors
            }
            similarity_ms = (perf_counter() - similarity_started) * 1000
            return ClusterSemanticScores(
                similarities=similarities,
                state="ready",
                model=self.model_name,
                model_version=self.model_version,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                candidate_pairs=len(pairs),
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                timings_ms={
                    "model_load": round(model_load_ms, 2),
                    "candidate_cache_lookup": batch_stats.cache_lookup_ms,
                    "candidate_embedding_generation": batch_stats.generation_ms,
                    "similarity": round(similarity_ms, 2),
                },
                batch_size=batch_stats.batch_size,
            )
        except Exception as error:
            self._model_error = self._safe_error(error)
            return self._empty_cluster("unavailable", started, pairs, self._model_error)

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                from fastembed import TextEmbedding

                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="The model .* now uses mean pooling instead of CLS embedding.*",
                        category=UserWarning,
                    )
                    self._model = TextEmbedding(
                        model_name=self.model_name,
                        cache_dir=str(self.cache_dir),
                        threads=self.threads,
                        local_files_only=self.local_files_only,
                    )
            return self._model

    def _content_key(self, document: SemanticDocument) -> str:
        payload = "\0".join(
            (
                self.model_name,
                self.model_version,
                normalize_text(document.title or ""),
                normalize_text(document.text),
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _document_vectors(
        self, model: Any, documents: list[SemanticDocument]
    ) -> tuple[dict[int, Any], int, int, EmbeddingBatchStats]:
        missing: list[tuple[str, SemanticDocument]] = []
        vectors: dict[int, Any] = {}
        cache_hits = 0
        lookup_started = perf_counter()
        with self._lock:
            for document in documents:
                cache_key = self._content_key(document)
                cached = self._embeddings.get(cache_key)
                if cached is None:
                    missing.append((cache_key, document))
                else:
                    self._embeddings.move_to_end(cache_key)
                    vectors[document.key] = cached
                    cache_hits += 1
        cache_lookup_ms = (perf_counter() - lookup_started) * 1000
        generation_ms = 0.0
        batch_size = min(32, len(missing)) if missing else 0
        if missing:
            generation_started = perf_counter()
            encoded = model.embed(
                [f"{document.title or ''}. {document.text}" for _, document in missing],
                batch_size=batch_size,
            )
            with self._lock:
                for (cache_key, document), vector in zip(missing, encoded, strict=True):
                    self._embeddings[cache_key] = vector
                    self._embeddings.move_to_end(cache_key)
                    vectors[document.key] = vector
                while len(self._embeddings) > self.embedding_cache_size:
                    self._embeddings.popitem(last=False)
            generation_ms = (perf_counter() - generation_started) * 1000
        return (
            vectors,
            cache_hits,
            len(missing),
            EmbeddingBatchStats(
                cache_lookup_ms=round(cache_lookup_ms, 2),
                generation_ms=round(generation_ms, 2),
                batch_size=batch_size,
            ),
        )

    @staticmethod
    def _cosine(left: Any, right: Any) -> float:
        dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
        right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def _empty(
        self,
        state: str,
        query_type: str,
        started: float,
        detail: str | None = None,
    ) -> SemanticScores:
        return SemanticScores(
            scores={},
            similarities={},
            state=state,
            model=self.model_name if state not in {"disabled", "lexical_only"} else None,
            model_version=self.model_version if state not in {"disabled", "lexical_only"} else None,
            query_type=query_type,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            detail=detail,
        )

    def _empty_cluster(
        self,
        state: str,
        started: float,
        pairs: tuple[tuple[int, int], ...],
        detail: str | None = None,
    ) -> ClusterSemanticScores:
        return ClusterSemanticScores(
            similarities={},
            state=state,
            model=self.model_name if state not in {"disabled"} else None,
            model_version=self.model_version if state not in {"disabled"} else None,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            candidate_pairs=len(pairs),
            detail=detail,
        )

    @staticmethod
    def _safe_error(error: Exception) -> str:
        if isinstance(error, (FileNotFoundError, ImportError, ValueError)):
            return "Local semantic model is unavailable; lexical ranking remains active"
        return "Local semantic ranking could not start; lexical ranking remains active"


@lru_cache(maxsize=8)
def _shared_semantic_ranker(
    enabled: bool,
    model_name: str,
    model_version: str,
    cache_dir: str,
    local_files_only: bool,
    threads: int,
) -> LocalSemanticRanker:
    return LocalSemanticRanker(
        enabled=enabled,
        model_name=model_name,
        model_version=model_version,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        threads=threads,
    )


def build_semantic_ranker(settings: Any) -> LocalSemanticRanker:
    cache_dir = Path(settings.semantic_model_cache_dir)
    if not cache_dir.is_absolute():
        cache_dir = Path(__file__).resolve().parents[4] / cache_dir
    return _shared_semantic_ranker(
        settings.semantic_ranking_enabled,
        settings.semantic_model_name,
        settings.semantic_model_version,
        str(cache_dir),
        settings.semantic_local_files_only,
        settings.semantic_threads,
    )
