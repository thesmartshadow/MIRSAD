from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..connectors import BaseConnector
from ..models import SearchSession
from ..schemas import SearchJobEvent, SearchJobStarted, SearchRequest
from .search import SearchService

TERMINAL_EVENTS = {"search.completed", "search.partial", "search.failed"}


@dataclass(slots=True)
class SearchJob:
    job_id: str
    session_id: str
    created_monotonic: float
    event_limit: int
    events: deque[SearchJobEvent] = field(init=False)
    next_sequence: int = 1
    terminal: bool = False
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None

    def __post_init__(self) -> None:
        self.events = deque(maxlen=self.event_limit)

    def publish(self, event: str, data: dict[str, Any], elapsed_ms: float) -> None:
        message = SearchJobEvent(
            sequence=self.next_sequence,
            event=event,
            job_id=self.job_id,
            session_id=self.session_id,
            elapsed_ms=max(0.0, round(elapsed_ms, 2)),
            emitted_at=datetime.now(UTC),
            data=data,
        )
        self.next_sequence += 1
        self.events.append(message)
        self.terminal = event in TERMINAL_EVENTS
        self.wake.set()


class SearchJobCapacityError(RuntimeError):
    pass


class SearchJobRegistry:
    """Bounded, process-local transport state for live search progress."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        ttl_seconds: int,
        max_entries: int,
        event_limit: int,
    ) -> None:
        self._session_factory = session_factory
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.event_limit = event_limit
        self._jobs: dict[str, SearchJob] = {}

    @property
    def size(self) -> int:
        self.cleanup()
        return len(self._jobs)

    def start(
        self,
        request: SearchRequest,
        settings: Settings,
        connectors: dict[str, BaseConnector],
    ) -> SearchJobStarted:
        self.cleanup()
        if len(self._jobs) >= self.max_entries:
            completed = sorted(
                (job for job in self._jobs.values() if job.terminal),
                key=lambda item: item.created_monotonic,
            )
            if completed:
                self._jobs.pop(completed[0].job_id, None)
            else:
                raise SearchJobCapacityError("The live search job limit has been reached")
        job = SearchJob(
            job_id=str(uuid4()),
            session_id=str(uuid4()),
            created_monotonic=monotonic(),
            event_limit=self.event_limit,
        )
        self._jobs[job.job_id] = job
        job.task = asyncio.create_task(
            self._run(job, request, settings, connectors),
            name=f"mirsad-search-{job.job_id[:8]}",
        )
        return SearchJobStarted(job_id=job.job_id, session_id=job.session_id)

    def get(self, job_id: str) -> SearchJob | None:
        self.cleanup()
        return self._jobs.get(job_id)

    def cleanup(self) -> None:
        now = monotonic()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.terminal and now - job.created_monotonic >= self.ttl_seconds
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)

    async def events(self, job: SearchJob) -> AsyncIterator[str]:
        sequence = 0
        while True:
            # Clear before observing history so a publish after the snapshot cannot be lost.
            job.wake.clear()
            available = [event for event in job.events if event.sequence > sequence]
            for event in available:
                sequence = event.sequence
                payload = event.model_dump_json()
                yield f"id: {sequence}\nevent: {event.event}\ndata: {payload}\n\n"
            if job.terminal and sequence >= job.next_sequence - 1:
                return
            try:
                await asyncio.wait_for(job.wake.wait(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"

    async def shutdown(self) -> None:
        tasks = [job.task for job in self._jobs.values() if job.task and not job.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(
        self,
        job: SearchJob,
        request: SearchRequest,
        settings: Settings,
        connectors: dict[str, BaseConnector],
    ) -> None:
        started = perf_counter()

        def emit(event: str, data: dict[str, Any]) -> None:
            # Validate transport metadata before it enters the SSE history.
            safe_data = json.loads(json.dumps(data, ensure_ascii=False, default=str))
            job.publish(event, safe_data, (perf_counter() - started) * 1000)

        try:
            with self._session_factory() as db:
                service = SearchService(db, settings, connectors, event_sink=emit)
                await service.execute(request, session_id=job.session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            with self._session_factory() as db:
                session = db.get(SearchSession, job.session_id)
                if session is not None and session.status == "running":
                    session.status = "failed"
                    session.completed_at = datetime.now(UTC)
                    session.warnings = [
                        {
                            "source": "mirsad",
                            "code": "internal_search_failure",
                            "message": "Search could not be completed",
                            "retryable": False,
                            "status_code": None,
                        }
                    ]
                    db.commit()
            emit(
                "search.failed",
                {
                    "code": "internal_search_failure",
                    "message": "Search could not be completed",
                },
            )


def make_search_job_registry(
    session_factory: sessionmaker[Session], settings: Settings
) -> SearchJobRegistry:
    return SearchJobRegistry(
        session_factory,
        ttl_seconds=settings.search_job_ttl_seconds,
        max_entries=settings.search_job_max_entries,
        event_limit=settings.search_job_event_limit,
    )
