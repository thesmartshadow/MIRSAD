from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..dependencies import Connectors, DbSession
from ..models import AuditEvent, Source, SourceHealth
from ..schemas import SourceStatus

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceUpdate(BaseModel):
    enabled: bool | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    github_scopes: list[str] | None = Field(default=None, min_length=1, max_length=3)


def _source_status(source: Source, health: SourceHealth | None) -> SourceStatus:
    detail = source.config_public.get("detail") if source.config_public else None
    acquisition_mode = str(source.config_public.get("active_acquisition_mode", "DIRECT_API"))
    configuration_state = str(
        source.config_public.get(
            "configuration_state", "configured" if source.configured else "unconfigured"
        )
    )
    if not source.enabled:
        current_status = "disabled"
    elif acquisition_mode == "WEB_INDEX" and configuration_state == "unconfigured":
        current_status = "web_discovery_disabled"
    else:
        current_status = health.status if health else "unknown"
    return SourceStatus(
        key=source.key,
        name=source.name,
        kind=source.kind,
        category=str(source.config_public.get("category", "developer_community")),
        support_level=str(source.config_public.get("support_level", "supported")),
        coverage_label=source.config_public.get("coverage_label"),
        capabilities=dict(source.config_public.get("capabilities", {})),
        configuration_state=configuration_state,
        active_acquisition_mode=acquisition_mode,
        enabled=source.enabled,
        configured=source.configured,
        status=current_status,
        detail=detail,
        confidence=source.confidence,
        last_checked_at=health.last_checked_at if health else None,
        last_success_at=health.last_success_at if health else None,
        recent_failure=health.recent_failure if health else None,
        failure_category=health.failure_category if health else None,
        http_status=health.http_status if health else None,
        average_latency_ms=round(health.average_latency_ms, 2) if health else 0,
        last_latency_ms=round(health.last_latency_ms, 2) if health else 0,
        last_result_count=health.last_result_count if health else 0,
        last_normalized_count=health.last_normalized_count if health else 0,
        last_malformed_count=health.last_malformed_count if health else 0,
        request_count=health.request_count if health else 0,
        failure_count=health.failure_count if health else 0,
        configuration={
            "scopes": source.config_public.get("scopes", []) if source.key == "github" else [],
            "credential_status": "configured"
            if source.configured
            else str(source.config_public.get("configuration_state", "unconfigured")),
        },
    )


@router.get("", response_model=list[SourceStatus])
async def list_sources(db: DbSession, connectors: Connectors) -> list[SourceStatus]:
    # Source rows preserve provenance after a connector is removed or disabled in
    # configuration. The management inventory must reflect the active registry,
    # not stale rows retained for historical content.
    rows = db.execute(
        select(Source, SourceHealth)
        .outerjoin(SourceHealth, SourceHealth.source_id == Source.id)
        .where(Source.key.in_(connectors))
        .order_by(Source.name)
    ).all()
    return [_source_status(source, health) for source, health in rows]


@router.patch("/{source_key}", response_model=SourceStatus)
async def update_source(
    source_key: str, payload: SourceUpdate, db: DbSession, connectors: Connectors
) -> SourceStatus:
    source = db.scalar(select(Source).where(Source.key == source_key))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.confidence is not None:
        source.confidence = payload.confidence
    if payload.github_scopes is not None:
        if source_key != "github":
            raise HTTPException(status_code=422, detail="Scopes are supported only for GitHub")
        connector = connectors.get("github")
        valid = set(getattr(connector, "VALID_SCOPES", ()))
        if not connector or set(payload.github_scopes) - valid:
            raise HTTPException(status_code=422, detail="Invalid GitHub search scopes")
        connector.set_scopes(payload.github_scopes)
        source.config_public = {
            **(source.config_public or {}),
            "scopes": list(connector.scopes),
        }
    db.add(
        AuditEvent(
            event_type="settings_changed",
            message="Source settings changed",
            context={
                "source": source_key,
                "enabled": source.enabled,
                "confidence": source.confidence,
                "github_scopes": source.config_public.get("scopes")
                if source_key == "github"
                else None,
            },
        )
    )
    db.commit()
    health = db.scalar(select(SourceHealth).where(SourceHealth.source_id == source.id))
    return _source_status(source, health)


@router.post("/health", response_model=list[SourceStatus])
async def refresh_source_health(db: DbSession, connectors: Connectors) -> list[SourceStatus]:
    now = datetime.now(UTC)
    for key, connector in connectors.items():
        source = db.scalar(select(Source).where(Source.key == key))
        if source is None:
            continue
        result = await connector.health_check()
        health = db.scalar(select(SourceHealth).where(SourceHealth.source_id == source.id))
        if health is None:
            health = SourceHealth(source_id=source.id)
            db.add(health)
        diagnostics = connector.last_diagnostics
        probe_status = str(result["status"])
        # Several connectors intentionally avoid spending quota in health_check.
        # Their "unknown" means no request was made, not that a previously
        # observed runtime state should be discarded.
        if probe_status != "unknown" or diagnostics.attempt_count:
            health.status = probe_status
            health.last_checked_at = now
        if diagnostics.attempt_count:
            health.http_status = diagnostics.http_status
            health.last_latency_ms = diagnostics.total_latency_ms
        if probe_status == "healthy":
            health.last_success_at = now
            health.recent_failure = None
            health.failure_category = None
        elif probe_status not in {"unknown", "unconfigured", "restricted"}:
            health.recent_failure = str(result.get("detail") or "Source health probe failed")
            health.failure_category = str(result["status"])
    db.commit()
    return await list_sources(db, connectors)
