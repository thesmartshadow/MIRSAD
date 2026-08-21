from __future__ import annotations

import asyncio
import gc
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from mirsad_api.config import Settings
from mirsad_api.connectors import (
    BaseConnector,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
)
from mirsad_api.connectors.gdelt import GdeltConnector
from mirsad_api.database import init_database, make_engine
from mirsad_api.models import SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.search import SearchService

ROOT = Path(__file__).resolve().parents[1]


class TimedConnector(BaseConnector):
    def __init__(
        self,
        key: str,
        delay_seconds: float,
        *,
        fail: bool = False,
        item_count: int = 1,
    ) -> None:
        self.metadata = ConnectorMetadata(
            key=key,
            name=f"Evidence {key}",
            kind="fixture",
            base_url=f"https://{key}.evidence.invalid",
            confidence=70,
        )
        super().__init__(timeout=max(0.1, delay_seconds + 0.1), retries=0)
        self.delay_seconds = delay_seconds
        self.fail = fail
        self.item_count = item_count
        self.completed_at: float | None = None

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        started = perf_counter()
        await asyncio.sleep(self.delay_seconds)
        self.completed_at = perf_counter()
        self.last_diagnostics = ConnectorDiagnostics(
            attempt_count=1,
            attempt_latencies_ms=[round((self.completed_at - started) * 1000, 2)],
            total_latency_ms=(self.completed_at - started) * 1000,
        )
        if self.fail:
            raise ConnectorError(self.metadata.key, "timeout", "Injected bounded timeout")
        items = [
            ConnectorItem(
                source=self.metadata.key,
                external_id=f"{self.metadata.key}-{index}",
                canonical_url=f"{self.metadata.base_url}/{index}",
                author="Evidence fixture",
                title=f"{query} evidence item {index}",
                text=f"Deterministic {query} content for concurrency evidence item {index}.",
                published_at=datetime.now(UTC),
                language="en",
                raw_metadata={"source_type": "fixture"},
            )
            for index in range(min(limit, self.item_count))
        ]
        self.last_diagnostics.raw_result_count = len(items)
        self.last_diagnostics.fetched_result_count = len(items)
        self.last_diagnostics.schema_valid_count = len(items)
        self.last_diagnostics.query_match_count = len(items)
        self.last_diagnostics.time_eligible_count = len(items)
        self.last_diagnostics.normalized_result_count = len(items)
        return items

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        raise NotImplementedError


async def measure_gdelt_budget() -> dict[str, Any]:
    intervals: list[tuple[float, float]] = []

    async def timeout_response(request: httpx.Request) -> httpx.Response:
        attempt_started = perf_counter()
        await asyncio.sleep(0.02)
        attempt_finished = perf_counter()
        intervals.append((attempt_started, attempt_finished))
        raise httpx.ReadTimeout("deterministic timeout", request=request)

    connector = GdeltConnector(
        timeout=1,
        retries=1,
        total_budget_seconds=0.35,
        circuit_failure_threshold=2,
        circuit_cooldown_seconds=10,
        transport=httpx.MockTransport(timeout_response),
    )
    searches: list[dict[str, Any]] = []
    for query in ("public policy", "open data"):
        intervals.clear()
        started = perf_counter()
        try:
            await connector.search(query, limit=10)
        except ConnectorError as error:
            elapsed = perf_counter() - started
            attempt_durations = [(end - start) * 1000 for start, end in intervals]
            backoff = (intervals[1][0] - intervals[0][1]) * 1000 if len(intervals) > 1 else None
            searches.append(
                {
                    "query": query,
                    "error_category": error.code,
                    "attempt_count": connector.last_diagnostics.attempt_count,
                    "attempt_durations_ms": [round(value, 2) for value in attempt_durations],
                    "retry_backoff_ms": round(backoff, 2) if backoff is not None else None,
                    "total_wall_clock_ms": round(elapsed * 1000, 2),
                    "configured_total_budget_ms": round(connector.total_budget_seconds * 1000, 2),
                    "circuit_breaker_state": connector.last_diagnostics.circuit_breaker_state,
                }
            )
    open_started = perf_counter()
    try:
        await connector.search("third request", limit=10)
    except ConnectorError as error:
        open_elapsed_ms = (perf_counter() - open_started) * 1000
        open_result = {
            "error_category": error.code,
            "wall_clock_ms": round(open_elapsed_ms, 3),
            "attempt_count": connector.last_diagnostics.attempt_count,
            "circuit_breaker_state": connector.last_diagnostics.circuit_breaker_state,
        }
    return {
        "configured_per_attempt_timeout_ms": connector.timeout * 1000,
        "configured_total_connector_budget_ms": connector.total_budget_seconds * 1000,
        "searches": searches,
        "open_circuit_response": open_result,
    }


async def measure_first_useful_result() -> dict[str, Any]:
    with TemporaryDirectory(prefix="mirsad-first-result-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'evidence.db'}"
        engine = make_engine(database_url)
        init_database(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        connectors = {
            "fast": TimedConnector("fast", 0.03),
            "medium": TimedConnector("medium", 0.09),
            "slow": TimedConnector("slow", 0.18, fail=True),
        }
        settings = Settings(database_url=database_url, enable_mock_connector=False)
        with factory() as db:
            seed_database(db, connectors)
            started = perf_counter()
            session_id = await SearchService(db, settings, connectors).execute(
                SearchRequest(
                    query="public policy",
                    sources=list(connectors),
                    limit=10,
                )
            )
            completed = perf_counter()
            session = db.get(SearchSession, session_id)
            assert session is not None
            completion = {
                key: round((connector.completed_at - started) * 1000, 2)
                for key, connector in connectors.items()
                if connector.completed_at is not None
            }
            payload = {
                "source_completion_ms": completion,
                "first_useful_source_completion_ms": min(
                    completion[key] for key in ("fast", "medium")
                ),
                "first_result_available_to_current_api_ms": round((completed - started) * 1000, 2),
                "total_search_completion_ms": round((completed - started) * 1000, 2),
                "incremental_results_exposed": False,
                "session_status": session.status,
                "result_count": session.result_count,
                "warning_sources": [warning["source"] for warning in session.warnings],
            }
        engine.dispose()
    return payload


def _rss_kib() -> int:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise RuntimeError("VmRSS is unavailable")


async def observe_backend_memory() -> dict[str, Any]:
    with TemporaryDirectory(prefix="mirsad-memory-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'memory.db'}"
        engine = make_engine(database_url)
        init_database(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        connectors = {
            "memory_a": TimedConnector("memory_a", 0, item_count=5),
            "memory_b": TimedConnector("memory_b", 0, item_count=5),
        }
        settings = Settings(database_url=database_url, enable_mock_connector=False)
        snapshots: list[dict[str, int]] = []
        with factory() as db:
            seed_database(db, connectors)
            service = SearchService(db, settings, connectors)
            request = SearchRequest(query="public policy", sources=list(connectors), limit=10)
            await service.execute(request)
            gc.collect()
            snapshots.append({"completed_searches": 1, "rss_kib": _rss_kib()})
            for completed in range(2, 32):
                await service.execute(request)
                if completed in {10, 20, 30}:
                    gc.collect()
                    snapshots.append({"completed_searches": completed, "rss_kib": _rss_kib()})
            large_connector = TimedConnector("memory_large", 0, item_count=200)
            large_connectors = {"memory_large": large_connector}
            seed_database(db, large_connectors)
            await SearchService(db, settings, large_connectors).execute(
                SearchRequest(query="public policy", sources=["memory_large"], limit=200)
            )
            gc.collect()
            snapshots.append({"completed_searches": 31, "rss_kib": _rss_kib()})
            session_count = len(db.scalars(select(SearchSession.id)).all())
        engine.dispose()
    return {
        "method": "Linux process VmRSS after explicit Python garbage collection",
        "formal_leak_proof": False,
        "snapshots": snapshots,
        "observed_rss_range_kib": max(row["rss_kib"] for row in snapshots)
        - min(row["rss_kib"] for row in snapshots),
        "persisted_session_count": session_count,
    }


async def run() -> dict[str, Any]:
    return {
        "schema": "mirsad.evidence-gap-benchmark",
        "version": "1.0",
        "gdelt_budget": await measure_gdelt_budget(),
        "first_useful_result": await measure_first_useful_result(),
        "backend_memory_observation": await observe_backend_memory(),
    }


def main() -> None:
    payload = asyncio.run(run())
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "evidence-gap-benchmarks.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    gdelt = payload["gdelt_budget"]
    first_search = gdelt["searches"][0]
    second_search = gdelt["searches"][1]
    first = payload["first_useful_result"]
    memory = payload["backend_memory_observation"]
    markdown = "\n".join(
        [
            "# Evidence-Gap Benchmarks",
            "",
            "## GDELT Total Budget",
            "",
            f"- Per-attempt HTTP timeout: {gdelt['configured_per_attempt_timeout_ms']:.0f} ms",
            "- Strict connector budget, including retries and backoff: "
            f"{gdelt['configured_total_connector_budget_ms']:.0f} ms",
            f"- Search 1 attempts: {first_search['attempt_durations_ms']} ms",
            f"- Search 1 retry backoff: {first_search['retry_backoff_ms']} ms",
            f"- Search 1 total: {first_search['total_wall_clock_ms']} ms; circuit "
            f"{first_search['circuit_breaker_state']}",
            f"- Search 2 attempts: {second_search['attempt_durations_ms']} ms",
            f"- Search 2 retry backoff: {second_search['retry_backoff_ms']} ms",
            f"- Search 2 total: {second_search['total_wall_clock_ms']} ms; circuit "
            f"{second_search['circuit_breaker_state']}",
            "- Open-circuit response: "
            f"{gdelt['open_circuit_response']['wall_clock_ms']} ms with zero HTTP attempts",
            "",
            "The two measured searches are separate calls used to cross the repeated-failure "
            "threshold. Each call has one total budget; retry count cannot multiply that budget.",
            "",
            "## First Useful Result",
            "",
            f"- Source completion: {first['source_completion_ms']}",
            f"- First healthy connector completed: {first['first_useful_source_completion_ms']} ms",
            "- Result available through current request/response API: "
            f"{first['first_result_available_to_current_api_ms']} ms",
            f"- Final state: {first['session_status']} with {first['result_count']} results",
            "- Streaming: not exposed by the current architecture; the API returns after all "
            "bounded connector tasks complete. The final partial response retains healthy results "
            "and identifies the failed source.",
            "",
            "## Backend Memory Observation",
            "",
            f"- Snapshots: {memory['snapshots']}",
            f"- Observed RSS range: {memory['observed_rss_range_kib']} KiB",
            "- Scope: bounded observation only, not a formal retained-heap or leak proof.",
        ]
    )
    (report_dir / "evidence-gap-benchmarks.md").write_text(markdown + "\n", encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
