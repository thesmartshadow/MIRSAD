from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select, text

from ..dependencies import DbSession
from ..discovery.classifiers import classify_reddit_url, classify_threads_url, classify_x_url
from ..domains.deduplication import content_fingerprint
from ..domains.query import normalize_text, resolve_content_language
from ..models import (
    Bookmark,
    ContentItem,
    ContentMetric,
    DiscoveryCache,
    ResponseCache,
    Source,
)
from ..schemas import (
    ConfirmAction,
    DataActionResult,
    DataCounts,
    ManualImportCreate,
    ManualImportView,
)
from ..services.data_management import (
    audit_data_action,
    clear_history,
    data_counts,
    reset_local_data,
)

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/manual-import", response_model=ManualImportView, status_code=201)
async def manual_import(payload: ManualImportCreate, db: DbSession) -> ManualImportView:
    classified = next(
        (
            value
            for classifier in (classify_x_url, classify_threads_url, classify_reddit_url)
            if (value := classifier(payload.url)) is not None and value.is_content
        ),
        None,
    )
    if classified is None or classified.canonical_content_id is None:
        raise HTTPException(
            status_code=422,
            detail="Only validated public X, Threads, or Reddit post/comment URLs are accepted",
        )
    source = db.scalar(select(Source).where(Source.key == classified.platform))
    if source is None:
        raise HTTPException(status_code=503, detail="Source registry is not initialized")
    existing = db.scalar(
        select(ContentItem).where(
            ContentItem.source_id == source.id,
            ContentItem.external_id == classified.canonical_content_id,
        )
    )
    duplicate = existing is not None
    item = existing
    if item is None:
        normalized_title = normalize_text(payload.title or "")
        normalized_text = normalize_text(payload.selected_text)
        item = ContentItem(
            source_id=source.id,
            external_id=classified.canonical_content_id,
            canonical_url=classified.canonical_url,
            author=classified.author_handle,
            author_handle=classified.author_handle,
            author_verified=None,
            title=payload.title,
            text=payload.selected_text,
            published_at=None,
            language=resolve_content_language(
                None,
                f"{payload.title or ''} {payload.selected_text}",
            ),
            hashtags=None,
            mentions=None,
            media_type=classified.content_type.value,
            acquisition_mode="MANUAL_IMPORT",
            content_fingerprint=content_fingerprint(payload.title, payload.selected_text),
            raw_metadata={
                "manual_import": True,
                "operator_selected_visible_text": True,
                "network_fetch_performed": False,
                "content_type": classified.content_type.value,
            },
            normalized_title=normalized_title,
            normalized_text=normalized_text,
            normalized_author=normalize_text(classified.author_handle or ""),
        )
        db.add(item)
        db.flush()
        db.add(
            ContentMetric(
                content_item_id=item.id,
                raw_metrics={},
                like_count=None,
                view_count=None,
                comment_count=None,
                share_count=None,
                repost_count=None,
                reaction_count=None,
                normalized_engagement=0,
                adapter_version="manual-v1",
            )
        )
        db.commit()
    return ManualImportView(
        id=item.public_id,
        source=classified.platform,
        canonical_url=classified.canonical_url,
        acquisition_mode="MANUAL_IMPORT",
        duplicate=duplicate,
    )


@router.get("/counts", response_model=DataCounts)
async def get_data_counts(db: DbSession) -> DataCounts:
    return data_counts(db)


@router.post("/actions/{action}", response_model=DataActionResult)
async def perform_data_action(
    action: str, payload: ConfirmAction, db: DbSession
) -> DataActionResult:
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Explicit confirmation is required")
    if action == "clear_history":
        affected = clear_history(db)
    elif action == "clear_bookmarks":
        affected = db.execute(delete(Bookmark)).rowcount
    elif action == "clear_cache":
        affected = (db.execute(delete(ResponseCache)).rowcount or 0) + (
            db.execute(delete(DiscoveryCache)).rowcount or 0
        )
    elif action == "rebuild_fts":
        db.execute(text("INSERT INTO content_fts(content_fts) VALUES ('rebuild')"))
        affected = int(db.execute(text("SELECT count(*) FROM content_fts")).scalar_one())
    elif action == "reset_database":
        affected = reset_local_data(db)
    else:
        raise HTTPException(status_code=404, detail="Unknown data action")
    audit_data_action(db, action, int(affected or 0))
    db.commit()
    return DataActionResult(action=action, affected=int(affected or 0), counts=data_counts(db))
