from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from time import perf_counter

from ..domains.query import normalize_text
from ..domains.semantic import SemanticDocument, SemanticRanker, prepare_in_worker


@dataclass(frozen=True, slots=True)
class SemanticPreparationSummary:
    eligible_candidates: int = 0
    started: bool = False
    completed_candidates: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    wall_ms: float = 0.0
    overlap_window_ms: float = 0.0
    hidden_work_ms: float = 0.0
    batches: int = 0
    failed: bool = False
    detail: str | None = None

    def as_dict(self) -> dict[str, int | float | bool | str | None]:
        return {
            "precompute_eligible_candidates": self.eligible_candidates,
            "precompute_started": self.started,
            "precompute_completed": self.completed_candidates,
            "precompute_cache_hits": self.cache_hits,
            "precompute_cache_misses": self.cache_misses,
            "precompute_wall_ms": self.wall_ms,
            "overlap_window_ms": self.overlap_window_ms,
            "semantic_work_hidden_ms": self.hidden_work_ms,
            "precompute_batches": self.batches,
            "precompute_failed": self.failed,
            "precompute_detail": self.detail,
        }


class SemanticPreparationCoordinator:
    """Per-search bounded producer with one shared authoritative model worker."""

    def __init__(self, ranker: SemanticRanker, *, max_candidates: int) -> None:
        self.ranker = ranker
        self.max_candidates = max(0, min(max_candidates, 20))
        self._queue: asyncio.Queue[SemanticDocument] = asyncio.Queue(
            maxsize=max(1, self.max_candidates)
        )
        self._seen: set[str] = set()
        self._task: asyncio.Task[None] | None = None
        self._closed = False
        self._eligible = 0
        self._completed = 0
        self._hits = 0
        self._misses = 0
        self._wall_ms = 0.0
        self._batches = 0
        self._failed = False
        self._detail: str | None = None
        self._intervals: list[tuple[float, float]] = []

    @property
    def queued(self) -> int:
        return self._queue.qsize()

    @property
    def worker_count(self) -> int:
        return int(self._task is not None and not self._task.done())

    async def submit(self, documents: list[SemanticDocument]) -> int:
        if self._closed or self.max_candidates == 0:
            return 0
        accepted = 0
        for document in documents:
            if self._eligible >= self.max_candidates:
                break
            identity = self._identity(document)
            if identity in self._seen:
                continue
            self._seen.add(identity)
            self._queue.put_nowait(document)
            self._eligible += 1
            accepted += 1
        if accepted and (self._task is None or self._task.done()):
            self._task = asyncio.create_task(self._run(), name="semantic-preparation")
        return accepted

    async def finish(
        self,
        *,
        collection_started: float,
        collection_finished: float,
    ) -> SemanticPreparationSummary:
        if not self._closed:
            self._closed = True
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                self._failed = True
                self._detail = "Semantic preparation was cancelled"
        overlap = sum(
            max(0.0, min(ended, collection_finished) - max(started, collection_started))
            for started, ended in self._intervals
        ) * 1000
        return SemanticPreparationSummary(
            eligible_candidates=self._eligible,
            started=self._task is not None,
            completed_candidates=self._completed,
            cache_hits=self._hits,
            cache_misses=self._misses,
            wall_ms=round(self._wall_ms, 2),
            overlap_window_ms=round(overlap, 2),
            hidden_work_ms=round(min(self._wall_ms, overlap), 2),
            batches=self._batches,
            failed=self._failed,
            detail=self._detail,
        )

    async def cancel(self) -> None:
        self._closed = True
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self) -> None:
        while not self._queue.empty():
            value = self._queue.get_nowait()
            batch = [value]
            while len(batch) < 20:
                try:
                    following = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                batch.append(following)
            started = perf_counter()
            try:
                result = await prepare_in_worker(
                    self.ranker,
                    batch,
                )
            except Exception as error:  # pragma: no cover - defensive boundary
                self._failed = True
                self._detail = type(error).__name__
                continue
            ended = perf_counter()
            self._intervals.append((started, ended))
            self._wall_ms += result.duration_ms
            self._batches += 1
            self._hits += result.cache_hits
            self._misses += result.cache_misses
            if result.state == "ready":
                self._completed += len(batch)
            elif result.state not in {"empty", "disabled", "unsupported"}:
                self._failed = True
                self._detail = result.detail or result.state

    def _identity(self, document: SemanticDocument) -> str:
        method = getattr(self.ranker, "cache_identity", None)
        if callable(method):
            return str(method(document))
        payload = "\0".join(
            (normalize_text(document.title or ""), normalize_text(document.text))
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
