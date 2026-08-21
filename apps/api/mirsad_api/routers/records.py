from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, select

from ..dependencies import AppSettings, Connectors, DbSession
from ..mafer.learning import OutcomeRecorder
from ..models import (
    AuditEvent,
    Bookmark,
    ContentItem,
    SavedSearch,
    SearchResult,
    SearchSession,
    Source,
)
from ..schemas import (
    BookmarkCreate,
    BookmarkUpdate,
    BookmarkView,
    DuplicateGroupView,
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearchView,
    SearchResponse,
)
from ..services.exporting import build_export, export_csv
from ..services.read_models import get_search_response
from ..services.records import bookmark_views, duplicate_group_view, saved_search_view
from ..services.search import SearchService

router = APIRouter(tags=["records"])


@router.get("/saved-searches", response_model=list[SavedSearchView])
async def list_saved_searches(db: DbSession) -> list[SavedSearchView]:
    rows = db.scalars(select(SavedSearch).order_by(SavedSearch.updated_at.desc())).all()
    return [saved_search_view(row) for row in rows]


@router.post("/saved-searches", response_model=SavedSearchView, status_code=status.HTTP_201_CREATED)
async def create_saved_search(payload: SavedSearchCreate, db: DbSession) -> SavedSearchView:
    row = SavedSearch(
        name=payload.name,
        query=payload.configuration.query,
        configuration=payload.configuration.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()
    db.add(
        AuditEvent(
            event_type="saved_search_created",
            message="Saved search created",
            context={"saved_search_id": row.id},
        )
    )
    db.commit()
    return saved_search_view(row)


@router.patch("/saved-searches/{saved_id}", response_model=SavedSearchView)
async def rename_saved_search(
    saved_id: str, payload: SavedSearchUpdate, db: DbSession
) -> SavedSearchView:
    row = db.get(SavedSearch, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    row.name = payload.name
    row.updated_at = datetime.now(UTC)
    db.commit()
    return saved_search_view(row)


@router.post("/saved-searches/{saved_id}/duplicate", response_model=SavedSearchView)
async def duplicate_saved_search(saved_id: str, db: DbSession) -> SavedSearchView:
    row = db.get(SavedSearch, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    duplicate = SavedSearch(
        name=f"{row.name} (copy)",
        query=row.query,
        configuration=row.configuration,
    )
    db.add(duplicate)
    db.commit()
    return saved_search_view(duplicate)


@router.post("/saved-searches/{saved_id}/run", response_model=SearchResponse)
async def run_saved_search(
    saved_id: str, db: DbSession, settings: AppSettings, connectors: Connectors
) -> SearchResponse:
    row = db.get(SavedSearch, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    session_id = await SearchService(db, settings, connectors).execute(
        saved_search_view(row).configuration
    )
    return get_search_response(db, session_id)


@router.delete("/saved-searches/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(saved_id: str, db: DbSession) -> Response:
    result = db.execute(delete(SavedSearch).where(SavedSearch.id == saved_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Saved search not found")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/bookmarks", response_model=list[BookmarkView])
async def list_bookmarks(db: DbSession) -> list[BookmarkView]:
    return bookmark_views(db)


@router.post("/bookmarks", response_model=BookmarkView, status_code=status.HTTP_201_CREATED)
async def create_bookmark(payload: BookmarkCreate, db: DbSession) -> BookmarkView:
    item = db.scalar(select(ContentItem).where(ContentItem.public_id == payload.content_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Content record not found")
    existing = db.scalar(select(Bookmark).where(Bookmark.content_item_id == item.id))
    if existing:
        raise HTTPException(status_code=409, detail="Record is already bookmarked")
    if payload.search_session_id and db.get(SearchSession, payload.search_session_id) is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    bookmark = Bookmark(
        content_item_id=item.id,
        search_session_id=payload.search_session_id,
        note=payload.note.strip(),
    )
    db.add(bookmark)
    if payload.search_session_id:
        session = db.get(SearchSession, payload.search_session_id)
        result = db.scalar(
            select(SearchResult).where(
                SearchResult.search_session_id == payload.search_session_id,
                SearchResult.content_item_id == item.id,
            )
        )
        source = db.scalar(select(Source.key).where(Source.id == item.source_id))
        OutcomeRecorder(db).record(
            "RESULT_BOOKMARKED",
            session=session,
            item=item,
            rank=result.rank if result else None,
            source=source,
        )
    db.commit()
    return next(view for view in bookmark_views(db) if view.id == bookmark.id)


@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkView)
async def update_bookmark(bookmark_id: str, payload: BookmarkUpdate, db: DbSession) -> BookmarkView:
    bookmark = db.get(Bookmark, bookmark_id)
    if bookmark is None:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    bookmark.note = payload.note.strip()
    bookmark.updated_at = datetime.now(UTC)
    db.commit()
    return next(view for view in bookmark_views(db) if view.id == bookmark.id)


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(bookmark_id: str, db: DbSession) -> Response:
    result = db.execute(delete(Bookmark).where(Bookmark.id == bookmark_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/duplicate-groups/{group_id}", response_model=DuplicateGroupView)
async def get_duplicate_group(
    group_id: str,
    db: DbSession,
    sort: str = Query(default="newest", pattern="^(newest|source|engagement)$"),
) -> DuplicateGroupView:
    return duplicate_group_view(db, group_id, sort)


@router.get("/searches/{session_id}/export")
async def export_search(
    session_id: str,
    db: DbSession,
    format: str = Query(pattern="^(csv|json)$"),
) -> Response:
    payload = build_export(db, session_id)
    filename = f"mirsad-{payload['search']['id']}.{format}"
    if format == "csv":
        return Response(
            export_csv(payload),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
