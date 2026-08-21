from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..dependencies import DbSession
from ..models import SearchSession
from ..schemas import ClusterSummary
from ..services.read_models import analytics_snapshot, cluster_summaries, global_analytics_snapshot

router = APIRouter(tags=["analytics"])


@router.get("/analytics", response_model=dict[str, Any])
async def get_global_analytics(
    db: DbSession,
    scope: str = Query(default="all", pattern="^(all|24h|7d|30d)$"),
) -> dict[str, Any]:
    return global_analytics_snapshot(db, scope=scope)


@router.get("/analytics/{session_id}", response_model=dict[str, Any])
async def get_analytics(session_id: str, db: DbSession) -> dict[str, Any]:
    if db.get(SearchSession, session_id) is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    return analytics_snapshot(db, session_id)


@router.get("/clusters", response_model=list[ClusterSummary])
async def get_clusters(session_id: str, db: DbSession) -> list[ClusterSummary]:
    if db.get(SearchSession, session_id) is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    return cluster_summaries(db, session_id)
