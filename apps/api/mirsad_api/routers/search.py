from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..dependencies import AppSettings, Connectors, DbSession
from ..models import SearchSession
from ..schemas import SearchDiagnostics, SearchRequest, SearchResponse, SearchSummary
from ..services.read_models import get_search_response, history
from ..services.search import SearchService

router = APIRouter(prefix="/searches", tags=["search"])


@router.post("", response_model=SearchResponse, status_code=status.HTTP_201_CREATED)
async def create_search(
    payload: SearchRequest,
    db: DbSession,
    settings: AppSettings,
    connectors: Connectors,
) -> SearchResponse:
    service = SearchService(db, settings, connectors)
    session_id = await service.execute(payload)
    return get_search_response(db, session_id)


@router.get("/{session_id}", response_model=SearchResponse)
async def get_search(session_id: str, db: DbSession) -> SearchResponse:
    return get_search_response(db, session_id)


@router.get("/{session_id}/diagnostics", response_model=SearchDiagnostics)
async def get_search_diagnostics(session_id: str, db: DbSession) -> SearchDiagnostics:
    session = db.get(SearchSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    return SearchDiagnostics(session_id=session.id, diagnostics=session.diagnostics or {})


@router.get("", response_model=list[SearchSummary])
async def list_searches(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SearchSummary]:
    return history(db, limit=limit, offset=offset)
