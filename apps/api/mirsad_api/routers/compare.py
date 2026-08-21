from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..dependencies import DbSession
from ..models import SearchSession
from ..schemas import CompareRequest, CompareResponse
from ..services.read_models import analytics_snapshot, search_summary

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=CompareResponse)
async def compare_searches(payload: CompareRequest, db: DbSession) -> CompareResponse:
    left = db.get(SearchSession, payload.left_session_id)
    right = db.get(SearchSession, payload.right_session_id)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="One or both search sessions were not found")
    left_end = left.completed_at or left.started_at
    right_end = right.completed_at or right.started_at
    left_window = (left_end - left.started_at).total_seconds()
    right_window = (right_end - right.started_at).total_seconds()
    return CompareResponse(
        left=search_summary(db, left),
        right=search_summary(db, right),
        left_analytics=analytics_snapshot(db, left.id),
        right_analytics=analytics_snapshot(db, right.id),
        collection_window_warning=abs(left_window - right_window)
        > max(1, min(left_window, right_window) * 0.1),
    )
