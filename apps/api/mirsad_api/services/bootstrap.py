from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..connectors import BaseConnector
from ..models import Setting, Source, SourceHealth

DEFAULT_SETTINGS = {
    "general.default_result_limit": (50, "general"),
    "search.default_time_range": ("7d", "search"),
    "ranking.relevance": (0.35, "ranking"),
    "ranking.freshness": (0.20, "ranking"),
    "ranking.engagement": (0.15, "ranking"),
    "ranking.source_confidence": (0.10, "ranking"),
    "ranking.cross_source_presence": (0.10, "ranking"),
    "ranking.novelty": (0.10, "ranking"),
    "language.default": ("en", "language"),
    "appearance.theme": ("system", "appearance"),
    "data.retention_days": (90, "data"),
}


def seed_database(db: Session, connectors: dict[str, BaseConnector]) -> None:
    for connector in connectors.values():
        existing = db.scalar(select(Source).where(Source.key == connector.metadata.key))
        if existing is not None and connector.metadata.key == "github":
            scopes = (existing.config_public or {}).get("scopes")
            if isinstance(scopes, list) and hasattr(connector, "set_scopes"):
                connector.set_scopes(scopes)
        configured, detail = connector.validate_configuration()
        public_config = {
            "detail": detail,
            "requires_credentials": connector.metadata.requires_credentials,
            "category": connector.metadata.category,
            "support_level": connector.metadata.support_level,
            "coverage_label": connector.metadata.coverage_label,
            "capabilities": connector.metadata.capabilities.as_dict(),
            "configuration_state": connector.configuration_state(),
            "active_acquisition_mode": connector.active_acquisition_mode(),
        }
        if connector.metadata.key == "github":
            public_config["scopes"] = list(getattr(connector, "scopes", ("repositories",)))
        values = {
            "key": connector.metadata.key,
            "name": connector.metadata.name,
            "kind": connector.metadata.kind,
            "enabled": True,
            "configured": configured,
            "confidence": connector.metadata.confidence,
            "config_public": public_config,
        }
        db.execute(insert(Source).values(**values).on_conflict_do_nothing(index_elements=["key"]))
        source = db.scalar(select(Source).where(Source.key == connector.metadata.key))
        if source is not None:
            source.configured = configured
            source.config_public = values["config_public"]
            db.execute(
                insert(SourceHealth)
                .values(
                    source_id=source.id,
                    status="unknown" if configured else connector.configuration_state(),
                    average_latency_ms=0,
                    request_count=0,
                    failure_count=0,
                )
                .on_conflict_do_nothing(index_elements=["source_id"])
            )
            health = db.scalar(select(SourceHealth).where(SourceHealth.source_id == source.id))
            if (
                health is not None
                and not configured
                and health.status
                in {
                    "unknown",
                    "unconfigured",
                    "restricted",
                }
            ):
                health.status = connector.configuration_state()
    for key, (value, category) in DEFAULT_SETTINGS.items():
        db.execute(
            insert(Setting)
            .values(key=key, value=value, category=category, safe_for_client=True)
            .on_conflict_do_nothing(index_elements=["key"])
        )
    db.commit()
