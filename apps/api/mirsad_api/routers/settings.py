from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from ..dependencies import DbSession
from ..models import AuditEvent, Setting
from ..schemas import SettingsUpdate, SettingValue
from ..services.bootstrap import DEFAULT_SETTINGS

router = APIRouter(prefix="/settings", tags=["settings"])


def _client_settings(db: DbSession) -> list[SettingValue]:
    rows = db.scalars(
        select(Setting)
        .where(Setting.safe_for_client.is_(True))
        .order_by(Setting.category, Setting.key)
    ).all()
    return [SettingValue(key=row.key, value=row.value, category=row.category) for row in rows]


def _validate_ranking(values: dict[str, Any], db: DbSession) -> None:
    ranking_keys = [key for key in DEFAULT_SETTINGS if key.startswith("ranking.")]
    resolved: dict[str, float] = {}
    for key in ranking_keys:
        current = db.get(Setting, key)
        value = values.get(key, current.value if current else DEFAULT_SETTINGS[key][0])
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= float(value) <= 1
        ):
            raise HTTPException(status_code=422, detail=f"{key} must be between 0 and 1")
        resolved[key] = float(value)
    if abs(sum(resolved.values()) - 1.0) > 1e-6:
        raise HTTPException(status_code=422, detail="Enabled ranking weights must total 1.0")


def _validate_preferences(values: dict[str, Any]) -> None:
    bounded_integers = {
        "general.default_result_limit": (1, 200),
        "data.retention_days": (1, 3650),
    }
    enums = {
        "search.default_time_range": {"24h", "7d", "30d", "all"},
        "language.default": {"en", "ar"},
        "appearance.theme": {"light", "dark", "system"},
    }
    for key, (minimum, maximum) in bounded_integers.items():
        if key not in values:
            continue
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise HTTPException(
                status_code=422,
                detail=f"{key} must be an integer between {minimum} and {maximum}",
            )
    for key, allowed in enums.items():
        if key in values and values[key] not in allowed:
            raise HTTPException(status_code=422, detail=f"{key} has an unsupported value")


@router.get("", response_model=list[SettingValue])
async def list_settings(db: DbSession) -> list[SettingValue]:
    return _client_settings(db)


@router.put("", response_model=list[SettingValue])
async def update_settings(payload: SettingsUpdate, db: DbSession) -> list[SettingValue]:
    unknown = set(payload.values) - set(DEFAULT_SETTINGS)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"Unsupported setting keys: {', '.join(sorted(unknown))}"
        )
    _validate_ranking(payload.values, db)
    _validate_preferences(payload.values)
    for key, value in payload.values.items():
        setting = db.get(Setting, key)
        if setting is None:
            _, category = DEFAULT_SETTINGS[key]
            setting = Setting(key=key, value=value, category=category, safe_for_client=True)
            db.add(setting)
        else:
            setting.value = value
    db.add(
        AuditEvent(
            event_type="settings_changed",
            message="Application settings changed",
            context={"keys": sorted(payload.values)},
        )
    )
    db.commit()
    return _client_settings(db)


@router.post("/reset", response_model=list[SettingValue])
async def reset_settings(db: DbSession) -> list[SettingValue]:
    db.execute(delete(Setting).where(Setting.safe_for_client.is_(True)))
    for key, (value, category) in DEFAULT_SETTINGS.items():
        db.add(Setting(key=key, value=value, category=category, safe_for_client=True))
    db.add(
        AuditEvent(event_type="settings_changed", message="Application settings reset", context={})
    )
    db.commit()
    return _client_settings(db)
