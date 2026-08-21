from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Bookmark,
    ContentItem,
    ContentMetric,
    DuplicateGroup,
    DuplicateGroupMember,
    SavedSearch,
    SearchQuery,
    SearchSession,
    Source,
)
from ..schemas import (
    BookmarkView,
    DuplicateGroupView,
    DuplicateMemberView,
    SavedSearchView,
    SearchRequest,
)


def saved_search_view(row: SavedSearch) -> SavedSearchView:
    return SavedSearchView(
        id=row.id,
        name=row.name,
        configuration=SearchRequest.model_validate(row.configuration),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def bookmark_views(db: Session) -> list[BookmarkView]:
    rows = db.execute(
        select(Bookmark, ContentItem, Source, SearchSession, SearchQuery)
        .join(ContentItem, ContentItem.id == Bookmark.content_item_id)
        .join(Source, Source.id == ContentItem.source_id)
        .outerjoin(SearchSession, SearchSession.id == Bookmark.search_session_id)
        .outerjoin(SearchQuery, SearchQuery.id == SearchSession.query_id)
        .order_by(Bookmark.updated_at.desc())
    ).all()
    return [
        BookmarkView(
            id=bookmark.id,
            content_id=item.public_id,
            source=source.key,
            source_type=str((item.raw_metadata or {}).get("source_type", "record")),
            author=item.author,
            title=item.title,
            published_at=item.published_at,
            canonical_url=item.canonical_url,
            search_session_id=session.id if session else None,
            discovered_query=query.original_query if query else None,
            note=bookmark.note,
            created_at=bookmark.created_at,
            updated_at=bookmark.updated_at,
        )
        for bookmark, item, source, session, query in rows
    ]


def duplicate_group_view(db: Session, group_id: str, sort: str) -> DuplicateGroupView:
    group = db.get(DuplicateGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Duplicate group not found")
    rows = db.execute(
        select(DuplicateGroupMember, ContentItem, Source, ContentMetric)
        .join(ContentItem, ContentItem.id == DuplicateGroupMember.content_item_id)
        .join(Source, Source.id == ContentItem.source_id)
        .outerjoin(ContentMetric, ContentMetric.content_item_id == ContentItem.id)
        .where(DuplicateGroupMember.duplicate_group_id == group_id)
    ).all()
    if sort == "source":
        rows.sort(
            key=lambda row: (
                row[2].key,
                -(row[1].published_at or datetime.min.replace(tzinfo=UTC)).timestamp(),
            )
        )
    elif sort == "engagement":
        rows.sort(key=lambda row: row[3].normalized_engagement if row[3] else 0, reverse=True)
    else:
        rows.sort(
            key=lambda row: (row[1].published_at or datetime.min.replace(tzinfo=UTC)).timestamp(),
            reverse=True,
        )
    representative = (
        db.get(ContentItem, group.canonical_item_id) if group.canonical_item_id else None
    )
    return DuplicateGroupView(
        id=group.id,
        source_count=group.source_count,
        source_names=group.source_names,
        record_count=group.record_count,
        earliest_seen=group.earliest_seen,
        latest_seen=group.latest_seen,
        representative_id=representative.public_id if representative else None,
        members=[
            DuplicateMemberView(
                id=item.public_id,
                source=source.key,
                source_type=str((item.raw_metadata or {}).get("source_type", "record")),
                author=item.author,
                title=item.title,
                text=item.text,
                canonical_url=item.canonical_url,
                published_at=item.published_at,
                engagement=metric.normalized_engagement if metric else 0,
                similarity=member.similarity,
                match_stage=member.match_stage,
                representative=item.id == group.canonical_item_id,
            )
            for member, item, source, metric in rows
        ],
    )
