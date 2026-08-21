from __future__ import annotations

import asyncio
import json
import math
import statistics
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from sqlalchemy.orm import sessionmaker

from mirsad_api.config import Settings
from mirsad_api.connectors import ConnectorItem, ConnectorMetadata, MockConnector
from mirsad_api.database import init_database, make_engine
from mirsad_api.domains.clustering import cluster_items
from mirsad_api.domains.deduplication import DeduplicationItem, find_duplicate_groups
from mirsad_api.domains.query import normalize_text, process_query
from mirsad_api.domains.ranking import calculate_score
from mirsad_api.models import SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.search import SearchService


class BenchmarkConnector(MockConnector):
    def __init__(self, key: str) -> None:
        self.metadata = ConnectorMetadata(
            key=key,
            name=f"Benchmark {key}",
            kind="fixture",
            base_url=f"mock://{key}",
            confidence=70,
        )
        super().__init__(latency=0.05)

    async def search(self, query: str, *, limit: int, since=None) -> list[ConnectorItem]:
        items = await super().search(query, limit=limit, since=since)
        return [
            replace(
                item,
                source=self.metadata.key,
                external_id=f"{self.metadata.key}:{item.external_id}",
                canonical_url=item.canonical_url.replace(
                    "mirsad-fixture/", f"mirsad-fixture/{self.metadata.key}/"
                ),
            )
            for item in items
        ]


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent) - 1)]


def engine_scaling() -> list[dict[str, float | int | None]]:
    query = process_query("public policy")
    weights = Settings().ranking_weights
    output: list[dict[str, float | int | None]] = []
    for size in (100, 200, 1_000, 5_000, 10_000):
        texts = [f"Public policy record unique{i} topic{i}" for i in range(size)]
        started = perf_counter()
        normalized = [normalize_text(value) for value in texts]
        normalization_ms = (perf_counter() - started) * 1000

        started = perf_counter()
        for index, value in enumerate(normalized):
            calculate_score(
                query=query,
                title=value,
                text=f"Detailed {value} analysis",
                canonical_url=f"https://benchmark.invalid/{index}",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
                engagement=10,
                source_confidence=70,
                bm25_normalized=50,
                weights=weights,
                now=datetime(2026, 1, 2, tzinfo=UTC),
            )
        ranking_ms = (perf_counter() - started) * 1000

        deduplication_ms: float | None = None
        clustering_ms: float | None = None
        if size <= 200:
            items = [
                DeduplicationItem(
                    key=index,
                    source="benchmark",
                    canonical_url=f"https://benchmark.invalid/{index}",
                    title=value,
                    text=f"Detailed {value} analysis",
                    published_at=None,
                )
                for index, value in enumerate(normalized)
            ]
            started = perf_counter()
            find_duplicate_groups(items)
            deduplication_ms = (perf_counter() - started) * 1000
            started = perf_counter()
            cluster_items(items)
            clustering_ms = (perf_counter() - started) * 1000
        output.append(
            {
                "records": size,
                "normalization_ms": round(normalization_ms, 2),
                "ranking_ms": round(ranking_ms, 2),
                "deduplication_ms": (
                    round(deduplication_ms, 2) if deduplication_ms is not None else None
                ),
                "clustering_ms": (
                    round(clustering_ms, 2) if clustering_ms is not None else None
                ),
            }
        )
    return output


async def benchmark(iterations: int = 12) -> dict:
    with TemporaryDirectory(prefix="mirsad-benchmark-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'benchmark.db'}"
        engine = make_engine(database_url)
        init_database(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        connectors = {
            key: BenchmarkConnector(key) for key in ("fixture_a", "fixture_b", "fixture_c")
        }
        settings = Settings(database_url=database_url, enable_mock_connector=False)
        observations: list[dict] = []
        with factory() as db:
            seed_database(db, connectors)
            for index in range(iterations + 1):
                started = perf_counter()
                session_id = await SearchService(db, settings, connectors).execute(
                    SearchRequest(
                        query=f"institutional public policy benchmark {index}",
                        sources=list(connectors),
                        limit=15,
                    )
                )
                wall_ms = (perf_counter() - started) * 1000
                session = db.get(SearchSession, session_id)
                assert session is not None
                if index:
                    observations.append(
                        {
                            "wall_ms": wall_ms,
                            "result_count": session.result_count,
                            "unique_count": session.unique_count,
                            **session.diagnostics["phase_timings_ms"],
                        }
                    )
        engine.dispose()

    wall = [row["wall_ms"] for row in observations]
    phases = {
        phase: round(statistics.median(row[phase] for row in observations), 2)
        for phase in (
            "connector_collection",
            "persistence",
            "deduplication",
            "ranking",
            "clustering",
        )
    }
    return {
        "schema": "mirsad.local-search-benchmark",
        "version": "1.0",
        "iterations": iterations,
        "fixture_connectors": 3,
        "per_connector_latency_ms": 50,
        "records_per_search": observations[0]["result_count"],
        "unique_records_per_search": observations[0]["unique_count"],
        "median_wall_ms": round(statistics.median(wall), 2),
        "p95_wall_ms": round(percentile(wall, 0.95), 2),
        "median_phase_ms": phases,
        "engine_scaling": engine_scaling(),
    }


def main() -> None:
    payload = asyncio.run(benchmark())
    output = Path("reports")
    output.mkdir(exist_ok=True)
    (output / "performance.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# Internal Engine Performance\n\n"
        "These are deterministic local measurements, not external network timings.\n\n"
        f"- Iterations: {payload['iterations']}\n"
        f"- Connectors: {payload['fixture_connectors']} concurrent fixtures at "
        f"{payload['per_connector_latency_ms']} ms each\n"
        f"- Records per search: {payload['records_per_search']} collected / "
        f"{payload['unique_records_per_search']} unique\n"
        f"- Median wall time: {payload['median_wall_ms']} ms\n"
        f"- P95 wall time: {payload['p95_wall_ms']} ms\n"
        f"- Median phases: {payload['median_phase_ms']}\n"
        f"- Transformation scaling: {payload['engine_scaling']}\n"
        "- Deduplication and clustering are measured at 100 and 200 records because interactive "
        "collection is capped at 200; larger values would not represent a production search.\n"
    )
    (output / "performance.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
