from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select, text

from ..dependencies import AppSettings, DbSession
from ..domains.semantic import build_semantic_ranker
from ..models import ContentItem, Source, SourceHealth
from ..schemas import SystemStatus

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system", response_model=SystemStatus)
async def system_status(db: DbSession, settings: AppSettings) -> SystemStatus:
    db.execute(text("SELECT 1"))
    database_integrity = str(db.execute(text("PRAGMA integrity_check")).scalar_one())
    foreign_key_violations = len(db.execute(text("PRAGMA foreign_key_check")).all())
    record_count = db.scalar(select(func.count(ContentItem.id))) or 0
    try:
        index_count = db.execute(text("SELECT count(*) FROM content_fts")).scalar_one()
        fts_status = "available"
    except Exception:
        index_count = 0
        fts_status = "unavailable"
    statuses = db.execute(
        select(
            Source.enabled, Source.configured, Source.config_public, SourceHealth.status
        ).outerjoin(SourceHealth, SourceHealth.source_id == Source.id)
    ).all()
    connector_status = {
        "available": 0,
        "degraded": 0,
        "unconfigured": 0,
        "disabled": 0,
        "unknown": 0,
    }
    for enabled, configured, public_config, health_status in statuses:
        configuration_state = (public_config or {}).get("configuration_state")
        state = (
            "disabled"
            if not enabled
            else "restricted"
            if configuration_state == "restricted"
            else "unconfigured"
            if not configured
            else health_status or "unknown"
        )
        connector_status[state] = connector_status.get(state, 0) + 1
    semantic_state, _semantic_detail = build_semantic_ranker(settings).capability_state()
    return SystemStatus(
        api_status="operational",
        database_status="available",
        fts_status=fts_status,
        connector_status=connector_status,
        record_count=record_count,
        index_count=index_count,
        database_integrity=database_integrity,
        foreign_key_violations=foreign_key_violations,
        capabilities=[
            "fts5",
            "bm25",
            "arabic_normalization",
            "deduplication",
            "explainable_scoring",
            "clustering",
            "social_capability_metadata",
            "platform_specific_engagement",
            "social_reach",
            "local_outcome_feedback",
            "adaptive_shadow_only",
            "evidence_graph",
            f"semantic_ranking:{semantic_state}",
        ],
        version=settings.version,
    )
