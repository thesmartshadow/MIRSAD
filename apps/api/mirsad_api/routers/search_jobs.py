from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ..dependencies import AppSettings, Connectors
from ..schemas import SearchJobStarted, SearchRequest
from ..services.search_jobs import SearchJobCapacityError, SearchJobRegistry

router = APIRouter(prefix="/search/jobs", tags=["search"])


def _registry(request: Request) -> SearchJobRegistry:
    return request.app.state.search_jobs


@router.post("", response_model=SearchJobStarted, status_code=status.HTTP_202_ACCEPTED)
async def create_search_job(
    payload: SearchRequest,
    request: Request,
    settings: AppSettings,
    connectors: Connectors,
) -> SearchJobStarted:
    try:
        return _registry(request).start(payload, settings, connectors)
    except SearchJobCapacityError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error


@router.get("/{job_id}/events")
async def stream_search_events(job_id: str, request: Request) -> StreamingResponse:
    job = _registry(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Search job not found or expired")
    return StreamingResponse(
        _registry(request).events(job),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        },
    )
