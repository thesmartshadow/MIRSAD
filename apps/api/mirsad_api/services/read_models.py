from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domains.analytics import build_analytics
from ..domains.engagement import social_reach
from ..models import (
    AnalyticsRecord,
    Cluster,
    ClusterMember,
    ContentItem,
    ContentMetric,
    ContentScore,
    DuplicateGroup,
    DuplicateGroupMember,
    SearchQuery,
    SearchResult,
    SearchSession,
    Source,
)
from ..schemas import (
    ClusterSummary,
    ConnectorWarning,
    CoverageReport,
    HighlightRange,
    ScoreExplanation,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SearchSummary,
)


def coverage_snapshot(session: SearchSession) -> CoverageReport:
    raw = (session.diagnostics or {}).get("coverage")
    if raw:
        return CoverageReport.model_validate(raw)
    connector_rows = list((session.diagnostics or {}).get("connectors") or ())
    represented = sorted(
        {
            str(row.get("source"))
            for row in connector_rows
            if int(row.get("final_top_results") or 0) > 0
        }
    )
    return CoverageReport.model_validate(
        {
            "session_id": session.id,
            "outcome_status": session.status,
            "coverage_status": "LIMITED",
            "sources": [
                {
                    "source": str(row.get("source")),
                    "selected": True,
                    "executed": True,
                    "contributed": int(row.get("final_top_results") or 0) > 0,
                    "status": str(row.get("status") or "UNKNOWN").upper(),
                    "acquisition_mode": row.get("acquisition_mode"),
                    "requests": int(row.get("attempt_count") or 0),
                    "fetched": int(row.get("fetched_results") or 0),
                    "matched": int(row.get("final_matching_results") or 0),
                    "admitted": int(row.get("candidate_admitted_results") or 0),
                    "final": int(row.get("final_top_results") or 0),
                }
                for row in connector_rows
            ],
            "lanes": [
                {
                    "lane": "LIVE",
                    "available": bool(connector_rows),
                    "executed": bool(connector_rows),
                    "contributed": bool(represented),
                    "candidates": sum(
                        int(row.get("candidate_admitted_results") or 0) for row in connector_rows
                    ),
                    "final": session.result_count,
                    "platforms": represented,
                },
                {
                    "lane": "LOCAL_MEMORY",
                    "available": True,
                    "executed": False,
                    "contributed": False,
                    "platforms": [],
                },
                {
                    "lane": "HISTORICAL",
                    "available": False,
                    "executed": False,
                    "contributed": False,
                    "platforms": [],
                },
            ],
            "gaps": [],
            "represented_platforms": represented,
            "web_discovery": "UNKNOWN",
            "stop_reason": (session.diagnostics or {}).get("mafer", {}).get("stop_reason"),
            "stop_explanation": "Coverage predates the v1.2 persisted coverage model.",
        }
    )


def relevant_snippet(
    text: str, matched_terms: list[str], *, max_length: int = 360
) -> tuple[str, list[HighlightRange]]:
    """Return plain text plus ranges; retrieved markup is never emitted as HTML."""

    plain = " ".join(text.split())
    terms = sorted(
        {term.strip() for term in matched_terms if term.strip()},
        key=len,
        reverse=True,
    )
    first_match: re.Match[str] | None = None
    for term in terms:
        match = re.search(re.escape(term), plain, flags=re.IGNORECASE)
        if match is not None and (first_match is None or match.start() < first_match.start()):
            first_match = match
    start = max(0, (first_match.start() - 90) if first_match else 0)
    end = min(len(plain), start + max_length)
    if end - start < max_length:
        start = max(0, end - max_length)
    prefix = "..." if start else ""
    suffix = "..." if end < len(plain) else ""
    body = plain[start:end]
    snippet = f"{prefix}{body}{suffix}"
    ranges: list[tuple[int, int]] = []
    for term in terms:
        for match in re.finditer(re.escape(term), body, flags=re.IGNORECASE):
            ranges.append((len(prefix) + match.start(), len(prefix) + match.end()))
    merged: list[tuple[int, int]] = []
    for range_start, range_end in sorted(ranges):
        if merged and range_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], range_end))
        else:
            merged.append((range_start, range_end))
    return snippet, [HighlightRange(start=left, end=right) for left, right in merged]


def search_summary(db: Session, session: SearchSession) -> SearchSummary:
    query = db.get(SearchQuery, session.query_id)
    if query is None:
        raise HTTPException(status_code=500, detail="Search query record is missing")
    parameters = dict(session.parameters or {})
    parameters.setdefault("query", query.original_query)
    parameters.setdefault("sources", session.sources or ["hacker_news"])
    parameters.setdefault("exact_phrase", query.exact_phrase)
    outcome = dict((session.diagnostics or {}).get("outcome") or {})
    return SearchSummary(
        id=session.id,
        original_query=query.original_query,
        normalized_query=query.normalized_query,
        detected_language=query.detected_language,
        status=session.status,
        sources=session.sources,
        result_count=session.result_count,
        unique_count=session.unique_count,
        duration_ms=session.duration_ms,
        started_at=session.started_at,
        completed_at=session.completed_at,
        warnings=[ConnectorWarning.model_validate(item) for item in session.warnings],
        parameters=SearchRequest.model_validate(parameters),
        outcome_reason=outcome.get("reason"),
        outcome_context=outcome,
    )


def analytics_snapshot(db: Session, session_id: str) -> dict[str, Any]:
    row = db.scalar(
        select(AnalyticsRecord).where(
            AnalyticsRecord.search_session_id == session_id,
            AnalyticsRecord.metric_key == "snapshot",
        )
    )
    snapshot = dict(row.value) if row else {}
    session = db.get(SearchSession, session_id)
    if session is None:
        return snapshot
    query = db.get(SearchQuery, session.query_id)
    duplicate_groups = db.scalars(
        select(DuplicateGroup).where(
            DuplicateGroup.search_session_id == session_id,
            DuplicateGroup.record_count > 1,
        )
    ).all()
    snapshot.update(
        {
            "scope": "session",
            "scope_session_id": session_id,
            "scope_query": query.original_query if query else None,
            "scope_started_at": session.started_at.isoformat(),
            "content_record_count": session.result_count,
            "unique_canonical_count": session.unique_count,
            "search_appearance_count": session.result_count,
            "duplicate_group_count": len(duplicate_groups),
            "scored_record_count": session.result_count,
        }
    )
    return snapshot


def global_analytics_snapshot(
    db: Session, *, scope: str = "all", now: datetime | None = None
) -> dict[str, Any]:
    """Aggregate canonical persisted content, never transient frontend state."""

    current = now or datetime.now(UTC)
    since_by_scope = {
        "24h": current - timedelta(hours=24),
        "7d": current - timedelta(days=7),
        "30d": current - timedelta(days=30),
    }
    since = since_by_scope.get(scope)
    content_query = (
        select(ContentItem, ContentMetric, Source)
        .join(Source, Source.id == ContentItem.source_id)
        .outerjoin(ContentMetric, ContentMetric.content_item_id == ContentItem.id)
        .order_by(ContentItem.id)
    )
    if since is not None:
        content_query = content_query.where(ContentItem.fetched_at >= since)
    rows = db.execute(content_query).all()
    content_ids = [item.id for item, _metric, _source in rows]

    latest_scores: dict[int, float] = {}
    if content_ids:
        score_rows = db.execute(
            select(ContentScore.content_item_id, ContentScore.final_score, ContentScore.id)
            .where(ContentScore.content_item_id.in_(content_ids))
            .order_by(ContentScore.id)
        ).all()
        for content_id, score, _score_id in score_rows:
            latest_scores[content_id] = score

    items: list[dict[str, Any]] = []
    for item, metric, source in rows:
        category = str((source.config_public or {}).get("category", "developer_community"))
        has_metrics = bool(metric and metric.raw_metrics)
        items.append(
            {
                "source": source.key,
                "score": latest_scores.get(item.id),
                "published_at": item.published_at,
                "language": item.language,
                "title": item.title,
                "text": item.text,
                "id": item.public_id,
                "category": category,
                "hashtags": item.hashtags,
                "mentions": item.mentions,
                "engagement": metric.normalized_engagement if metric else None,
                "has_engagement_metrics": has_metrics,
                "social_reach": (
                    social_reach(source.key, metric.normalized_engagement, 1)
                    if metric and has_metrics
                    else None
                ),
            }
        )

    session_query = select(SearchSession)
    if since is not None:
        session_query = session_query.where(SearchSession.started_at >= since)
    sessions = db.scalars(session_query).all()
    session_ids = [session.id for session in sessions]
    search_appearances = 0
    cluster_sizes: list[int] = []
    duplicate_groups: list[DuplicateGroup] = []
    if session_ids:
        search_appearances = len(
            db.scalars(
                select(SearchResult.id).where(SearchResult.search_session_id.in_(session_ids))
            ).all()
        )
        cluster_sizes = list(
            db.scalars(
                select(Cluster.member_count).where(Cluster.search_session_id.in_(session_ids))
            ).all()
        )
        duplicate_groups = list(
            db.scalars(
                select(DuplicateGroup).where(
                    DuplicateGroup.search_session_id.in_(session_ids),
                    DuplicateGroup.record_count > 1,
                )
            ).all()
        )

    duplicate_member_ids: set[int] = set()
    if duplicate_groups:
        canonical_by_group = {
            group.id: group.canonical_item_id for group in duplicate_groups
        }
        member_rows = db.execute(
            select(DuplicateGroupMember.duplicate_group_id, DuplicateGroupMember.content_item_id)
            .where(
                DuplicateGroupMember.duplicate_group_id.in_(canonical_by_group),
                DuplicateGroupMember.content_item_id.in_(content_ids),
            )
        ).all()
        duplicate_member_ids = {
            content_id
            for group_id, content_id in member_rows
            if content_id != canonical_by_group[group_id]
        }

    canonical_urls = {item.canonical_url for item, _metric, _source in rows}
    average_duration = round(
        sum(session.duration_ms for session in sessions) / max(1, len(sessions))
    )
    analytics = build_analytics(
        items,
        unique_count=len(canonical_urls),
        duration_ms=average_duration,
        cluster_sizes=cluster_sizes,
        bucket="24h" if scope == "30d" else "6h" if scope == "7d" else "1h",
        bucket_count=30 if scope == "30d" else 28 if scope == "7d" else 24,
        include_all_time=scope == "all",
    )
    analytics.update(
        {
            "scope": scope,
            "scope_since": since.isoformat() if since else None,
            "content_record_count": len(rows),
            "unique_canonical_count": len(canonical_urls),
            "search_appearance_count": search_appearances,
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_count": len(duplicate_member_ids),
            "cluster_count": len(cluster_sizes),
            "scored_record_count": len(latest_scores),
            "search_session_count": len(sessions),
        }
    )
    return analytics


def cluster_summaries(db: Session, session_id: str) -> list[ClusterSummary]:
    clusters = db.scalars(
        select(Cluster)
        .where(Cluster.search_session_id == session_id)
        .order_by(Cluster.aggregate_score.desc())
    ).all()
    member_ids_by_cluster: dict[str, list[str]] = {cluster.id: [] for cluster in clusters}
    if member_ids_by_cluster:
        member_rows = db.execute(
            select(ClusterMember.cluster_id, ContentItem.public_id)
            .join(ContentItem, ClusterMember.content_item_id == ContentItem.id)
            .where(ClusterMember.cluster_id.in_(member_ids_by_cluster))
        ).all()
        for cluster_id, item_id in member_rows:
            member_ids_by_cluster[cluster_id].append(item_id)
    output: list[ClusterSummary] = []
    for cluster in clusters:
        output.append(
            ClusterSummary(
                id=cluster.id,
                representative_title=cluster.representative_title,
                member_count=cluster.member_count,
                source_distribution=cluster.source_distribution,
                platform_presence=cluster.source_distribution,
                platform_diversity=cluster.platform_diversity,
                first_seen_by_mirsad=cluster.earliest_at,
                earliest_at=cluster.earliest_at,
                latest_at=cluster.latest_at,
                aggregate_score=cluster.aggregate_score,
                terms=cluster.terms,
                member_ids=member_ids_by_cluster[cluster.id],
            )
        )
    return output


def get_search_response(db: Session, session_id: str) -> SearchResponse:
    session = db.get(SearchSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    rows = db.execute(
        select(SearchResult, ContentItem, ContentMetric, ContentScore, Source)
        .join(ContentItem, ContentItem.id == SearchResult.content_item_id)
        .join(Source, Source.id == ContentItem.source_id)
        .join(ContentMetric, ContentMetric.content_item_id == ContentItem.id)
        .join(
            ContentScore,
            (ContentScore.content_item_id == ContentItem.id)
            & (ContentScore.search_session_id == SearchResult.search_session_id),
        )
        .where(SearchResult.search_session_id == session_id)
        .order_by(SearchResult.rank)
    ).all()
    group_ids = {row[0].duplicate_group_id for row in rows if row[0].duplicate_group_id}
    groups = (
        {
            group.id: group
            for group in db.scalars(
                select(DuplicateGroup).where(DuplicateGroup.id.in_(group_ids))
            ).all()
        }
        if group_ids
        else {}
    )
    results: list[SearchResultItem] = []
    for result, item, metric, score, source in rows:
        group = groups.get(result.duplicate_group_id)
        raw_evidence = (item.raw_metadata or {}).get("evidence_completeness")
        evidence_level = (
            str(raw_evidence.get("level", "UNKNOWN"))
            if isinstance(raw_evidence, dict)
            else str(raw_evidence or "UNKNOWN")
        )
        evidence_score = (
            float(raw_evidence["score"])
            if isinstance(raw_evidence, dict)
            and isinstance(raw_evidence.get("score"), (int, float))
            else None
        )
        snippet, highlight_ranges = relevant_snippet(item.text, score.matched_terms)
        results.append(
            SearchResultItem(
                id=item.public_id,
                source=source.key,
                source_type=str((item.raw_metadata or {}).get("source_type", "record")),
                acquisition_mode=item.acquisition_mode,
                acquisition_path=result.acquisition_path or item.acquisition_mode,
                acquisition_paths=list(
                    result.acquisition_paths
                    or [result.acquisition_path or item.acquisition_mode]
                ),
                acquisition_modes_seen=list(
                    (item.raw_metadata or {}).get("acquisition_modes_seen")
                    or [item.acquisition_mode]
                ),
                indexed_public_web_coverage=bool(
                    (item.raw_metadata or {}).get("indexed_public_web_coverage", False)
                ),
                discovery_support=(item.raw_metadata or {}).get("discovery_support"),
                discovery_engines=list(
                    (item.raw_metadata or {}).get("engines_that_found_it") or ()
                ),
                evidence_completeness=evidence_level,
                evidence_completeness_score=evidence_score,
                external_id=item.external_id,
                canonical_url=item.canonical_url,
                author=item.author,
                author_handle=item.author_handle,
                author_verified=item.author_verified,
                title=item.title,
                text=item.text,
                relevant_snippet=snippet,
                highlight_ranges=highlight_ranges,
                semantic_only_match=bool(
                    not highlight_ranges
                    and (score.explanation or {}).get("semantic_relevance") is not None
                ),
                published_at=item.published_at,
                fetched_at=item.fetched_at,
                first_seen_at=item.first_seen_at,
                last_seen_at=item.last_seen_at,
                retrieved_at=item.retrieved_at,
                language=item.language,
                hashtags=item.hashtags,
                mentions=item.mentions,
                media_type=item.media_type,
                like_count=metric.like_count,
                view_count=metric.view_count,
                comment_count=metric.comment_count,
                share_count=metric.share_count,
                repost_count=metric.repost_count,
                reaction_count=metric.reaction_count,
                raw_metrics=metric.raw_metrics,
                normalized_engagement=metric.normalized_engagement,
                social_reach=(
                    social_reach(
                        source.key,
                        metric.normalized_engagement,
                        len(group.source_names) if group else 1,
                    )
                    if metric.raw_metrics
                    else None
                ),
                score=score.final_score,
                matched_terms=score.matched_terms,
                duplicate_group_id=result.duplicate_group_id,
                duplicate_count=(group.record_count - 1) if group else 0,
                related_sources=group.source_names if group else [source.key],
                cluster_id=result.cluster_id,
                explanation=ScoreExplanation(
                    final_score=score.final_score,
                    relevance=score.relevance,
                    freshness=score.freshness,
                    engagement=score.engagement,
                    source_confidence=score.source_confidence,
                    cross_source_presence=score.cross_source_presence,
                    novelty=score.novelty,
                    spam_penalty=score.spam_penalty,
                    supporting_signal_factor=float(
                        (score.explanation or {}).get("supporting_signal_factor", 1.0)
                    ),
                    pre_penalty_score=(score.explanation or {}).get("pre_penalty_score"),
                    weighted_components=(score.explanation or {}).get("weighted_components", {}),
                    lexical_relevance=float(
                        (score.explanation or {}).get("lexical_relevance", score.relevance)
                    ),
                    semantic_relevance=(score.explanation or {}).get("semantic_relevance"),
                    semantic_similarity=(score.explanation or {}).get("semantic_similarity"),
                    semantic_weight=float((score.explanation or {}).get("semantic_weight", 0.0)),
                    secondary_quality_budget=float(
                        (score.explanation or {}).get("secondary_quality_budget", 0.0)
                    ),
                    ranking_strategy=str(
                        (score.explanation or {}).get("ranking_strategy", "lexical_explainable")
                    ),
                    semantic_state=str(
                        (score.explanation or {}).get("semantic_state", "not_applied")
                    ),
                    relevance_features=(score.explanation or {}).get("relevance_features", {}),
                    matched_terms=score.matched_terms,
                    source=source.key,
                    fetched_at=item.fetched_at,
                    published_at=item.published_at,
                    duplicate_group_id=result.duplicate_group_id,
                ),
            )
        )
    return SearchResponse(
        session=search_summary(db, session),
        results=results,
        clusters=cluster_summaries(db, session_id),
        analytics=analytics_snapshot(db, session_id),
        coverage=coverage_snapshot(session),
    )


def history(db: Session, *, limit: int = 50, offset: int = 0) -> list[SearchSummary]:
    sessions = db.scalars(
        select(SearchSession).order_by(SearchSession.started_at.desc()).offset(offset).limit(limit)
    ).all()
    return [search_summary(db, session) for session in sessions]
