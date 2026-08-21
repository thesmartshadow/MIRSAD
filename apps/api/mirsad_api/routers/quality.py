from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..dependencies import DbSession
from ..mafer.configuration import (
    ensure_configuration_snapshots,
    rollback_one_step,
)
from ..mafer.learning import OutcomeRecorder, ShadowUtilityLearner
from ..models import (
    AlgorithmConfigurationSnapshot,
    ContentItem,
    EngineUtilityObservation,
    SearchOutcomeEvent,
    SearchQuery,
    SearchResult,
    SearchSession,
    ShadowEvaluation,
    Source,
)
from ..schemas import (
    OutcomeEventCreate,
    OutcomeEventView,
    QualitySummary,
    RollbackRequest,
)

router = APIRouter(prefix="/quality", tags=["quality"])


def _event_view(row: SearchOutcomeEvent, item: ContentItem | None) -> OutcomeEventView:
    return OutcomeEventView(
        id=row.id,
        event_type=row.event_type,
        search_session_id=row.search_session_id,
        content_id=item.public_id if item else None,
        query_class=row.query_class,
        rank=row.rank,
        source=row.source,
        acquisition_mode=row.acquisition_mode,
        explicit_judgment=row.explicit_judgment,
        created_at=row.created_at,
    )


@router.post("/events", response_model=OutcomeEventView, status_code=status.HTTP_201_CREATED)
async def create_outcome_event(payload: OutcomeEventCreate, db: DbSession) -> OutcomeEventView:
    session = db.get(SearchSession, payload.search_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    item = None
    result = None
    if payload.content_id:
        item = db.scalar(select(ContentItem).where(ContentItem.public_id == payload.content_id))
        if item is None:
            raise HTTPException(status_code=404, detail="Content record not found")
        result = db.scalar(
            select(SearchResult).where(
                SearchResult.search_session_id == session.id,
                SearchResult.content_item_id == item.id,
            )
        )
        if result is None:
            raise HTTPException(status_code=409, detail="Result does not belong to this search")
    elif payload.event_type != "SEARCH_REFORMULATED":
        raise HTTPException(status_code=422, detail="This event requires a content result")
    source = None
    if item:
        source = db.scalar(select(Source.key).where(Source.id == item.source_id))
    row = OutcomeRecorder(db).record(
        payload.event_type,
        session=session,
        item=item,
        rank=result.rank if result else None,
        source=source,
        context={
            **payload.context,
            **(
                {
                    "discovery_engines": list(
                        (item.raw_metadata or {}).get("engines_that_found_it", [])
                    )[:10]
                }
                if item
                else {}
            ),
        },
    )
    db.commit()
    return _event_view(row, item)


@router.get("", response_model=QualitySummary)
async def quality_summary(db: DbSession) -> QualitySummary:
    sessions = db.scalars(select(SearchSession)).all()
    events = db.scalars(select(SearchOutcomeEvent)).all()
    query_languages = Counter(
        db.scalars(
            select(SearchQuery.detected_language).join(
                SearchSession, SearchSession.query_id == SearchQuery.id
            )
        ).all()
    )
    query_classes = Counter(
        event.query_class for event in events if event.event_type == "SEARCH_EXECUTED"
    )
    stop_reasons: Counter[str] = Counter()
    uncertainties: Counter[str] = Counter()
    rounds: list[int] = []
    requests: list[int] = []
    for session in sessions:
        mafer = (session.diagnostics or {}).get("mafer", {})
        if mafer.get("stop_reason"):
            stop_reasons[str(mafer["stop_reason"])] += 1
        searches = [value for value in mafer.get("rounds", []) if value.get("round", 0) > 0]
        rounds.append(len(searches))
        requests.append(int(mafer.get("requests_used", 0)))
        if searches:
            level = searches[-1].get("uncertainty", {}).get("level")
            if level:
                uncertainties[str(level)] += 1
    source_utility = [
        value.as_dict()
        for value in sorted(
            ShadowUtilityLearner(db).source_utilities().values(),
            key=lambda value: (value.query_class, value.source),
        )
    ]
    engine_rows = db.scalars(select(EngineUtilityObservation)).all()
    engine_utility = [
        {
            "engine": engine,
            "target_platform": platform,
            "query_class": query_class,
            "requests": len(rows_for_key),
            "available": sum(row.available for row in rows_for_key),
            "canonical_yield": sum(row.canonical_yield for row in rows_for_key),
            "latency_ms": round(sum(row.latency_ms for row in rows_for_key) / len(rows_for_key), 2),
        }
        for (engine, platform, query_class), rows_for_key in _group_engine_rows(engine_rows).items()
    ]
    snapshots = db.scalars(
        select(AlgorithmConfigurationSnapshot)
        .where(AlgorithmConfigurationSnapshot.active)
        .order_by(AlgorithmConfigurationSnapshot.slot)
    ).all()
    shadow_counts = dict(
        db.execute(
            select(ShadowEvaluation.strategy_type, func.count(ShadowEvaluation.id)).group_by(
                ShadowEvaluation.strategy_type
            )
        ).all()
    )
    zero_count = sum(event.event_type == "ZERO_RESULT" for event in events)
    return QualitySummary(
        search_count=len(sessions),
        zero_result_count=zero_count,
        zero_result_rate=round(zero_count / max(1, len(sessions)), 4),
        explicit_relevant=sum(event.explicit_judgment == "relevant" for event in events),
        explicit_not_relevant=sum(event.explicit_judgment == "not_relevant" for event in events),
        query_class_distribution=dict(query_classes),
        language_distribution=dict(query_languages),
        source_utility=source_utility,
        engine_utility=engine_utility,
        average_rounds=round(sum(rounds) / max(1, len(rounds)), 2),
        stop_reasons=dict(stop_reasons),
        uncertainty_distribution=dict(uncertainties),
        average_latency_ms=round(
            sum(session.duration_ms for session in sessions) / max(1, len(sessions)), 2
        ),
        average_request_count=round(sum(requests) / max(1, len(requests)), 2),
        shadow_comparisons=shadow_counts,
        configuration_snapshots=[
            {
                "id": row.id,
                "slot": row.slot,
                "reason": row.reason,
                "created_at": row.created_at.isoformat(),
                "configuration": row.configuration,
            }
            for row in snapshots
        ],
    )


def _group_engine_rows(
    rows: list[EngineUtilityObservation],
) -> dict[tuple[str, str, str], list[EngineUtilityObservation]]:
    groups: dict[tuple[str, str, str], list[EngineUtilityObservation]] = {}
    for row in rows:
        groups.setdefault((row.engine, row.target_platform, row.query_class), []).append(row)
    return groups


@router.post("/rollback", response_model=dict[str, str])
async def rollback_configuration(payload: RollbackRequest, db: DbSession) -> dict[str, str]:
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Rollback confirmation is required")
    try:
        row = rollback_one_step(db, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"status": "rolled_back", "snapshot_id": row.id}


@router.post("/configuration/initialize", response_model=dict[str, int])
async def initialize_configuration(db: DbSession) -> dict[str, int]:
    rows = ensure_configuration_snapshots(db)
    db.commit()
    return {"active_snapshots": len(rows)}
