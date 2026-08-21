from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mirsad_api.config import Settings
from mirsad_api.database import init_database, make_engine
from mirsad_api.mafer.configuration import ensure_configuration_snapshots
from mirsad_api.models import ContentItem, SearchQuery, SearchResult, SearchSession, Source
from mirsad_api.schemas import SearchRequest, TimeRange
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.registry import build_connector_registry
from mirsad_api.services.search import SearchService

OUTPUT = Path("reports/production-evidence")
SMOKE_QUERIES = (
    ("arabic_entity", "وزارة التخطيط", "balanced", False),
    ("arabic_topic", "الذكاء الاصطناعي", "fast", False),
    ("arabic_exact", "وزارة التخطيط", "deep", True),
    ("english_entity", "Microsoft", "fast", False),
    ("english_topic", "climate adaptation", "balanced", False),
    ("mixed_entity", "Microsoft العراق", "deep", False),
    ("hashtag", "#technology", "fast", False),
    ("identifier", "CVE-2025-55182", "balanced", False),
)


def _shadow_keys(diagnostics: dict[str, Any], strategy: str) -> list[int]:
    mafer = diagnostics.get("mafer") or {}
    ranking = mafer.get("shadow_ranking") or diagnostics.get("shadow_ranking") or {}
    values = ranking.get(strategy) or {}
    return [int(value) for value in values.get("ordered_keys") or []]


def build_judgment_pool(db: Session, sessions: list[SearchSession], *, depth: int = 10):
    queue: list[dict[str, Any]] = []
    for session in sessions:
        diagnostics = session.diagnostics or {}
        results = db.execute(
            select(SearchResult, ContentItem)
            .join(ContentItem, ContentItem.id == SearchResult.content_item_id)
            .where(SearchResult.search_session_id == session.id)
            .order_by(SearchResult.rank)
        ).all()
        by_id = {item.id: (result, item) for result, item in results}
        production = [item.id for result, item in results if result.rank <= depth]
        fusion = _shadow_keys(diagnostics, "fusion")[:depth]
        diversity = _shadow_keys(diagnostics, "near_tie_diversity")[:depth]
        union = list(dict.fromkeys(production + fusion + diversity))
        production_ranks = {key: index for index, key in enumerate(production, 1)}
        fusion_ranks = {key: index for index, key in enumerate(fusion, 1)}
        diversity_ranks = {key: index for index, key in enumerate(diversity, 1)}
        uncertainty = str(
            (diagnostics.get("mafer") or {})
            .get("post_ranking_uncertainty", {})
            .get("level", "UNKNOWN")
        )
        query = session.parameters.get("query", "")
        labels = (
            (diagnostics.get("mafer") or {}).get("intent_fingerprint", {}).get("labels", [])
        )
        for key in union:
            pair = by_id.get(key)
            if pair is None:
                continue
            _result, item = pair
            ranks = [
                rank
                for rank in (
                    production_ranks.get(key),
                    fusion_ranks.get(key),
                    diversity_ranks.get(key),
                )
                if rank is not None
            ]
            disagreement = max(ranks) - min(ranks) if len(ranks) > 1 else depth
            language_priority = 10 if any("\u0600" <= char <= "\u06ff" for char in query) else 0
            uncertainty_priority = (
                8 if uncertainty == "HIGH" else 4 if uncertainty == "MEDIUM" else 0
            )
            source = db.get(Source, item.source_id)
            queue.append(
                {
                    "queue_id": hashlib.sha256(f"{session.id}:{key}".encode()).hexdigest()[:20],
                    "search_session_id": session.id,
                    "content_id": item.public_id,
                    "query": query,
                    "query_class": labels[0] if labels else "unknown",
                    "title": item.title,
                    "text": item.text,
                    "source": source.key if source else "unknown",
                    "acquisition_mode": item.acquisition_mode,
                    "canonical_url": item.canonical_url,
                    "production_rank": production_ranks.get(key),
                    "shadow_fusion_rank": fusion_ranks.get(key),
                    "shadow_diversity_rank": diversity_ranks.get(key),
                    "uncertainty": uncertainty,
                    "priority": disagreement + language_priority + uncertainty_priority,
                    "judgment": None,
                    "allowed_judgments": ["RELEVANT", "NOT_RELEVANT", "SKIP_UNSURE"],
                    "blind_display_fields": [
                        "query",
                        "title",
                        "text",
                        "source",
                        "canonical_url",
                    ],
                }
            )
    return sorted(queue, key=lambda item: (-item["priority"], item["queue_id"]))


async def run() -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    database_path = OUTPUT / "live-smoke.db"
    if database_path.exists():
        database_path.unlink()
    settings = Settings(database_url=f"sqlite:///{database_path}")
    engine = make_engine(settings.database_url)
    init_database(engine)
    registry = build_connector_registry(settings)
    sessions: list[SearchSession] = []
    evidence: list[dict[str, Any]] = []
    with Session(engine, expire_on_commit=False) as db:
        seed_database(db, registry)
        ensure_configuration_snapshots(db)
        service = SearchService(db, settings, registry)
        for query_id, query, mode, exact in SMOKE_QUERIES:
            session_id = await service.execute(
                SearchRequest(
                    query=query,
                    sources=["bluesky"],
                    source_selection="auto",
                    search_mode=mode,
                    exact_phrase=exact,
                    time_range=TimeRange.ALL,
                    limit=30,
                )
            )
            session = db.get(SearchSession, session_id)
            if session is None:
                raise RuntimeError("Search session was not persisted")
            sessions.append(session)
            diagnostics = session.diagnostics or {}
            mafer = diagnostics.get("mafer") or {}
            results = db.execute(
                select(SearchResult, ContentItem, Source)
                .join(ContentItem, ContentItem.id == SearchResult.content_item_id)
                .join(Source, Source.id == ContentItem.source_id)
                .where(SearchResult.search_session_id == session.id)
                .order_by(SearchResult.rank)
            ).all()
            evidence.append(
                {
                    "id": query_id,
                    "query": query,
                    "mode": mode.upper(),
                    "exact_phrase": exact,
                    "status": session.status,
                    "selected_sources": diagnostics.get("selected_sources", []),
                    "intent_fingerprint": mafer.get("intent_fingerprint"),
                    "query_lattice": mafer.get("query_lattice"),
                    "rounds": mafer.get("rounds"),
                    "stop_reason": mafer.get("stop_reason"),
                    "external_failures": [
                        {
                            "source": item.get("source"),
                            "status": item.get("status"),
                            "error_category": item.get("error_category"),
                        }
                        for item in diagnostics.get("connectors", [])
                        if item.get("error_category")
                    ],
                    "result_count": session.result_count,
                    "unique_count": session.unique_count,
                    "top_result_urls": [
                        item.canonical_url for _result, item, _source in results[:10]
                    ],
                    "source_distribution": dict(
                        Counter(source.key for _result, _item, source in results)
                    ),
                    "latency_ms": session.duration_ms,
                    "phase_timings_ms": diagnostics.get("phase_timings_ms"),
                    "semantic_state": (diagnostics.get("ranking") or {}).get("semantic_state"),
                    "shadow_ranking": mafer.get("shadow_ranking"),
                }
            )
        queue = build_judgment_pool(db, sessions)
        db.commit()
        integrity = db.connection().exec_driver_sql("PRAGMA integrity_check").scalar_one()
        foreign_keys = len(db.connection().exec_driver_sql("PRAGMA foreign_key_check").all())
        content_count = int(db.scalar(select(func.count(ContentItem.id))) or 0)
    engine.dispose()
    payload = {
        "schema": "mirsad.production-live-search-smoke",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "production_strategy": "MAFER Phase 2 deterministic",
        "searches": evidence,
        "judgment_pool_size": len(queue),
        "database": {
            "path": str(database_path),
            "integrity": integrity,
            "foreign_key_violations": foreign_keys,
            "content_items": content_count,
            "size_bytes": database_path.stat().st_size,
        },
    }
    smoke_path = OUTPUT / "live-search-smoke.json"
    queue_path = OUTPUT / "judgment-queue.json"
    smoke_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["artifacts"] = {
        smoke_path.name: hashlib.sha256(smoke_path.read_bytes()).hexdigest(),
        queue_path.name: hashlib.sha256(queue_path.read_bytes()).hexdigest(),
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded live production search smoke")
    parser.add_argument("--refresh-existing", action="store_true")
    args = parser.parse_args()
    if args.refresh_existing:
        database_path = OUTPUT / "live-smoke.db"
        smoke_path = OUTPUT / "live-search-smoke.json"
        queue_path = OUTPUT / "judgment-queue.json"
        payload = json.loads(smoke_path.read_text(encoding="utf-8"))
        engine = make_engine(f"sqlite:///{database_path}")
        with Session(engine) as db:
            sessions = db.scalars(
                select(SearchSession).order_by(SearchSession.started_at, SearchSession.id)
            ).all()
            queue = build_judgment_pool(db, sessions)
            for item in payload["searches"]:
                session = next(
                    (
                        session
                        for session in sessions
                        if db.get(SearchQuery, session.query_id).original_query == item["query"]
                        and bool(session.parameters.get("exact_phrase"))
                        == bool(item["exact_phrase"])
                    ),
                    None,
                )
                if session is None:
                    continue
                rows = db.execute(
                    select(SearchResult, Source)
                    .join(ContentItem, ContentItem.id == SearchResult.content_item_id)
                    .join(Source, Source.id == ContentItem.source_id)
                    .where(SearchResult.search_session_id == session.id)
                ).all()
                item["source_distribution"] = dict(Counter(source.key for _result, source in rows))
        engine.dispose()
        queue_path.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        payload["judgment_pool_size"] = len(queue)
        payload["artifacts"] = {
            queue_path.name: hashlib.sha256(queue_path.read_bytes()).hexdigest()
        }
        smoke_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
