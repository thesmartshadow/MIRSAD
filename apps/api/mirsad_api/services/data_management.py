from __future__ import annotations

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from ..models import (
    AnalyticsRecord,
    AuditEvent,
    Bookmark,
    Cluster,
    ClusterMember,
    ConnectorRunRecord,
    ContentItem,
    ContentMetric,
    ContentScore,
    DiscoveryCache,
    DiscoveryEngineStat,
    DiscoveryObservation,
    DiscoveryRecord,
    DuplicateGroup,
    DuplicateGroupMember,
    EngineUtilityObservation,
    EntityAliasEdge,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    ResponseCache,
    SavedSearch,
    SearchOutcomeEvent,
    SearchQuery,
    SearchResult,
    SearchSession,
    ShadowEvaluation,
    SourceHealth,
    SourceUtilityObservation,
)
from ..schemas import DataCounts


def data_counts(db: Session) -> DataCounts:
    return DataCounts(
        search_sessions=db.scalar(select(func.count(SearchSession.id))) or 0,
        content_items=db.scalar(select(func.count(ContentItem.id))) or 0,
        bookmarks=db.scalar(select(func.count(Bookmark.id))) or 0,
        saved_searches=db.scalar(select(func.count(SavedSearch.id))) or 0,
        cached_responses=(
            (db.scalar(select(func.count(ResponseCache.key))) or 0)
            + (db.scalar(select(func.count(DiscoveryCache.key))) or 0)
        ),
        indexed_records=int(db.execute(text("SELECT count(*) FROM content_fts")).scalar_one()),
    )


def clear_history(db: Session) -> int:
    count = db.scalar(select(func.count(SearchSession.id))) or 0
    db.execute(update(Bookmark).values(search_session_id=None))
    for model in (
        SearchOutcomeEvent,
        SourceUtilityObservation,
        EngineUtilityObservation,
        ShadowEvaluation,
        ClusterMember,
        DuplicateGroupMember,
        SearchResult,
        ContentScore,
        ConnectorRunRecord,
        AnalyticsRecord,
        Cluster,
        DuplicateGroup,
        SearchSession,
        SearchQuery,
    ):
        db.execute(delete(model))
    return count


def reset_local_data(db: Session) -> int:
    count = db.scalar(select(func.count(ContentItem.id))) or 0
    clear_history(db)
    for model in (
        EvidenceGraphEdge,
        EvidenceGraphNode,
        Bookmark,
        ContentMetric,
        ContentItem,
        ResponseCache,
        DiscoveryObservation,
        DiscoveryRecord,
        DiscoveryCache,
        DiscoveryEngineStat,
        EntityAliasEdge,
        SavedSearch,
    ):
        db.execute(delete(model))
    db.execute(
        update(SourceHealth).values(
            status="unknown",
            recent_failure=None,
            failure_category=None,
            http_status=None,
            average_latency_ms=0,
            last_latency_ms=0,
            last_result_count=0,
            last_normalized_count=0,
            last_malformed_count=0,
            request_count=0,
            failure_count=0,
        )
    )
    db.flush()
    db.execute(text("INSERT INTO content_fts(content_fts) VALUES ('rebuild')"))
    return count


def audit_data_action(db: Session, action: str, affected: int) -> None:
    db.add(
        AuditEvent(
            event_type="index_rebuilt" if action == "rebuild_fts" else "data_changed",
            message=f"Local data action completed: {action}",
            context={"action": action, "affected": affected},
        )
    )
