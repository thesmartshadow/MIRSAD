from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import statistics
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from mirsad_api.config import Settings
from mirsad_api.connectors import BaseConnector, ConnectorItem, ConnectorMetadata
from mirsad_api.database import init_database, make_engine
from mirsad_api.domains.query import process_query
from mirsad_api.domains.semantic import LocalSemanticRanker
from mirsad_api.mafer.planning import AdaptiveSearchPlanner
from mirsad_api.models import SearchResult, SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import get_search_response
from mirsad_api.services.search import SearchService


class StaticConnector(BaseConnector):
    def __init__(self, key: str, offset: int) -> None:
        self.metadata = ConnectorMetadata(
            key=key,
            name=f"Evolution {key}",
            kind="fixture",
            base_url=f"mock://{key}",
            confidence=70,
        )
        super().__init__()
        self.offset = offset

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    def normalize(self, payload: dict[str, object]) -> ConnectorItem:
        raise NotImplementedError

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        del query, since
        await asyncio.sleep(0.02)
        return [
            ConnectorItem(
                source=self.metadata.key,
                external_id=f"record-{self.offset + index}",
                canonical_url=f"https://benchmark.invalid/{self.offset + index}",
                author="Benchmark analyst",
                title=f"Public policy institutional governance record {self.offset + index}",
                text=(
                    "Public policy and institutional governance evidence for Arabic and English "
                    f"search performance record {self.offset + index}."
                ),
                published_at=datetime(2026, 8, 20, tzinfo=UTC),
                language="en",
                raw_metrics={},
                raw_metadata={"benchmark": True},
            )
            for index in range(min(limit, 15))
        ]


def rss_mib() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)


def median(values: list[float]) -> float:
    return round(statistics.median(values), 2) if values else 0.0


async def run() -> dict[str, object]:
    with TemporaryDirectory(prefix="mirsad-search-evolution-") as directory:
        database_path = Path(directory) / "evolution.db"
        database_url = f"sqlite:///{database_path}"
        engine = make_engine(database_url)
        init_database(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        connectors = {
            "evolution_a": StaticConnector("evolution_a", 0),
            "evolution_b": StaticConnector("evolution_b", 100),
        }
        settings = Settings(database_url=database_url, enable_mock_connector=False)
        ranker = LocalSemanticRanker(
            enabled=settings.semantic_ranking_enabled,
            model_name=settings.semantic_model_name,
            model_version=settings.semantic_model_version,
            cache_dir=str(Path(settings.semantic_model_cache_dir).resolve()),
            local_files_only=True,
            threads=settings.semantic_threads,
        )
        observations: list[dict[str, object]] = []
        with factory() as db:
            seed_database(db, connectors)
            cases = (
                ("cold", "public policy"),
                ("warm_repeat", "public policy"),
                ("warm_new_query_cached_content", "institutional governance"),
            )
            for label, query in cases:
                request = SearchRequest(
                    query=query,
                    sources=list(connectors),
                    source_selection="explicit",
                    time_range="all",
                    limit=20,
                )
                analysis_started = perf_counter()
                processed = process_query(query)
                query_analysis_ms = round((perf_counter() - analysis_started) * 1000, 3)
                planner_started = perf_counter()
                AdaptiveSearchPlanner(db, connectors).prepare(
                    processed,
                    selected_sources=request.sources,
                    source_selection=request.source_selection,
                    mode=request.search_mode,
                    explicit_time_range=request.time_range.value,
                )
                planner_ms = round((perf_counter() - planner_started) * 1000, 3)

                before_rss = rss_mib()
                wall_started = perf_counter()
                session_id = await SearchService(
                    db, settings, connectors, semantic_ranker=ranker
                ).execute(request)
                wall_ms = round((perf_counter() - wall_started) * 1000, 2)
                after_rss = rss_mib()
                session = db.get(SearchSession, session_id)
                assert session is not None

                result_ids = list(
                    db.scalars(
                        select(SearchResult.content_item_id).where(
                            SearchResult.search_session_id == session_id
                        )
                    ).all()
                )
                fts_started = perf_counter()
                SearchService(db, settings, connectors, semantic_ranker=ranker)._bm25_scores(
                    processed, result_ids
                )
                fts_ms = round((perf_counter() - fts_started) * 1000, 3)
                read_started = perf_counter()
                response = get_search_response(db, session_id)
                read_model_ms = round((perf_counter() - read_started) * 1000, 3)
                serialization_started = perf_counter()
                response.model_dump_json()
                serialization_ms = round((perf_counter() - serialization_started) * 1000, 3)
                phase = session.diagnostics.get("phase_timings_ms", {})
                semantic = session.diagnostics.get("ranking", {})
                observations.append(
                    {
                        "case": label,
                        "query": query,
                        "wall_ms": wall_ms,
                        "rss_before_mib": before_rss,
                        "rss_after_mib": after_rss,
                        "query_analysis_ms": query_analysis_ms,
                        "planner_probe_ms": planner_ms,
                        "fts_candidate_probe_ms": fts_ms,
                        "read_model_ms": read_model_ms,
                        "serialization_ms": serialization_ms,
                        "result_count": session.result_count,
                        "unique_count": session.unique_count,
                        "phase_timings_ms": phase,
                        "semantic": {
                            "state": semantic.get("semantic_state"),
                            "duration_ms": semantic.get("semantic_duration_ms"),
                            "candidate_count": semantic.get("semantic_candidate_count"),
                            "cache_hits": semantic.get("embedding_cache_hits"),
                            "cache_misses": semantic.get("embedding_cache_misses"),
                            "timings_ms": semantic.get("semantic_timings_ms", {}),
                            "batch_size": semantic.get("embedding_batch_size", 0),
                        },
                    }
                )

            query_plan = list(
                db.connection().exec_driver_sql(
                    "EXPLAIN QUERY PLAN SELECT rowid, bm25(content_fts) "
                    "FROM content_fts WHERE content_fts MATCH ? LIMIT 100",
                    ("public AND policy",),
                )
            )
        engine.dispose()

    return {
        "schema": "mirsad.search-evolution-baseline",
        "version": settings.version,
        "captured_at": datetime.now(UTC).isoformat(),
        "operator_database_used": False,
        "process_id": os.getpid(),
        "model": settings.semantic_model_name,
        "model_version": settings.semantic_model_version,
        "semantic_candidate_limit": settings.semantic_candidate_limit,
        "observations": observations,
        "summary": {
            "cold_semantic_ms": observations[0]["semantic"]["duration_ms"],
            "warm_repeat_semantic_ms": observations[1]["semantic"]["duration_ms"],
            "warm_new_query_semantic_ms": observations[2]["semantic"]["duration_ms"],
            "median_wall_ms": median([float(row["wall_ms"]) for row in observations]),
        },
        "fts_query_plan": [list(row) for row in query_plan],
        "baseline_instrumentation_gaps": [
            "model initialization is included in cold semantic duration",
            "query encoding and document encoding are not separately timed",
            "similarity time is included in semantic duration",
            "frontend feedback/render is not measured by the synchronous API harness",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="reports/search-evolution-baseline.json", type=Path
    )
    arguments = parser.parse_args()
    payload = asyncio.run(run())
    output = arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
