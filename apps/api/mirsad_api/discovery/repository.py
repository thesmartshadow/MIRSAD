from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import (
    DiscoveryCache,
    DiscoveryEngineStat,
    DiscoveryObservation,
    DiscoveryRecord,
)
from .models import DiscoveryCandidate, EngineTelemetry

SessionFactory = Callable[[], Session]


class DiscoveryRepository:
    def __init__(self, session_factory: SessionFactory, *, cache_max_entries: int = 500) -> None:
        self.session_factory = session_factory
        self.cache_max_entries = max(10, min(cache_max_entries, 5000))

    @staticmethod
    def cache_key(parts: dict[str, Any]) -> str:
        stable = "\n".join(f"{key}={parts[key]}" for key in sorted(parts))
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()

    def get_cache(self, key: str) -> tuple[dict[str, Any] | None, str]:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            entry = db.get(DiscoveryCache, key)
            if entry is None:
                return None, "fresh"
            if entry.expires_at <= now:
                return dict(entry.payload), "stale"
            return dict(entry.payload), "cached"

    def put_cache(
        self,
        key: str,
        platform: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            entry = db.get(DiscoveryCache, key)
            if entry is None:
                entry = DiscoveryCache(key=key, platform=platform, payload=payload)
                db.add(entry)
            entry.payload = payload
            entry.created_at = now
            entry.expires_at = now + timedelta(seconds=max(30, ttl_seconds))
            db.flush()
            count = int(db.scalar(select(func.count()).select_from(DiscoveryCache)) or 0)
            excess = count - self.cache_max_entries
            if excess > 0:
                oldest = db.scalars(
                    select(DiscoveryCache.key)
                    .order_by(DiscoveryCache.created_at.asc())
                    .limit(excess)
                ).all()
                if oldest:
                    db.execute(delete(DiscoveryCache).where(DiscoveryCache.key.in_(oldest)))
            db.commit()

    def remember(self, candidate: DiscoveryCandidate) -> None:
        now = datetime.now(UTC)
        fingerprint = hashlib.sha256(
            f"{candidate.indexed_title or ''}\n{candidate.indexed_snippet or ''}".encode()
        ).hexdigest()
        with self.session_factory() as db:
            record = db.scalar(
                select(DiscoveryRecord).where(
                    DiscoveryRecord.canonical_url == candidate.canonical_url
                )
            )
            if record is None:
                record = DiscoveryRecord(
                    platform=candidate.platform,
                    canonical_url=candidate.canonical_url,
                    content_type=candidate.content_type.value,
                    canonical_content_id=candidate.canonical_content_id,
                    indexed_title=candidate.indexed_title,
                    indexed_snippet=candidate.indexed_snippet,
                    acquisition_mode=candidate.acquisition_mode.value,
                    language_hint=candidate.language_hint,
                    published_at_hint=candidate.published_at_hint,
                    metadata_completeness=candidate.metadata_completeness,
                    content_fingerprint=fingerprint,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(record)
                db.flush()
            else:
                record.last_seen_at = now
                record.availability_state = "indexed"
                if candidate.metadata_completeness >= record.metadata_completeness:
                    record.indexed_title = candidate.indexed_title or record.indexed_title
                    record.indexed_snippet = candidate.indexed_snippet or record.indexed_snippet
                    record.language_hint = candidate.language_hint or record.language_hint
                    record.published_at_hint = (
                        candidate.published_at_hint or record.published_at_hint
                    )
                    record.metadata_completeness = candidate.metadata_completeness
                    record.content_fingerprint = fingerprint
            for engine in candidate.engines_that_found_it or (candidate.discovery_engine,):
                for variant in candidate.query_variants_that_found_it or (
                    candidate.query_variant_id,
                ):
                    exists = db.scalar(
                        select(DiscoveryObservation.id).where(
                            DiscoveryObservation.discovery_record_id == record.id,
                            DiscoveryObservation.engine == engine,
                            DiscoveryObservation.discovery_query == candidate.discovery_query,
                            DiscoveryObservation.query_variant_id == variant,
                        )
                    )
                    if exists is None:
                        db.add(
                            DiscoveryObservation(
                                discovery_record_id=record.id,
                                engine=engine,
                                discovery_query=candidate.discovery_query,
                                query_variant_id=variant,
                                discovered_at=now,
                            )
                        )
            db.commit()

    def support_for(self, canonical_url: str) -> tuple[tuple[str, ...], tuple[str, ...], int]:
        with self.session_factory() as db:
            record = db.scalar(
                select(DiscoveryRecord).where(DiscoveryRecord.canonical_url == canonical_url)
            )
            if record is None:
                return (), (), 0
            observations = db.scalars(
                select(DiscoveryObservation).where(
                    DiscoveryObservation.discovery_record_id == record.id
                )
            ).all()
            engines = tuple(sorted({item.engine for item in observations}))
            variants = tuple(sorted({item.query_variant_id for item in observations}))
            independent = len({(item.engine, item.query_variant_id) for item in observations})
            return engines, variants, independent

    def record_engine_telemetry(self, values: list[EngineTelemetry]) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as db:
            for item in values:
                row = db.scalar(
                    select(DiscoveryEngineStat).where(
                        DiscoveryEngineStat.engine == item.engine,
                        DiscoveryEngineStat.platform == item.target_platform,
                    )
                )
                if row is None:
                    row = DiscoveryEngineStat(
                        engine=item.engine,
                        platform=item.target_platform,
                        request_count=0,
                        returned_count=0,
                        target_domain_count=0,
                        accepted_canonical_count=0,
                        duplicate_count=0,
                        timeout_count=0,
                        rate_limit_count=0,
                        captcha_count=0,
                        error_count=0,
                        latency_total_ms=0.0,
                        current_state="UNKNOWN",
                    )
                    db.add(row)
                row.request_count += 1
                row.returned_count += item.returned_result_count
                row.target_domain_count += item.target_domain_result_count
                row.accepted_canonical_count += item.accepted_canonical_result_count
                row.duplicate_count += item.duplicate_count
                row.timeout_count += int(item.timeout)
                row.rate_limit_count += int(item.rate_limited)
                row.captcha_count += int("captcha" in (item.error or "").casefold())
                row.error_count += int(item.error is not None)
                row.latency_total_ms += item.latency_ms or 0.0
                row.current_state = item.current_state
                row.last_error = (item.error or "")[:300] or None
                row.last_seen_at = now
                if item.cooldown_remaining_seconds > 0:
                    row.cooldown_until = now + timedelta(seconds=item.cooldown_remaining_seconds)
            db.commit()

    def engine_performance(self, platform: str) -> dict[str, dict[str, float | str]]:
        with self.session_factory() as db:
            rows = db.scalars(
                select(DiscoveryEngineStat).where(DiscoveryEngineStat.platform == platform)
            ).all()
            return {
                row.engine: {
                    "request_count": row.request_count,
                    "current_state": row.current_state,
                    "target_domain_precision": (
                        row.target_domain_count / row.returned_count if row.returned_count else 0.0
                    ),
                    "canonical_yield": (
                        row.accepted_canonical_count / row.request_count
                        if row.request_count
                        else 0.0
                    ),
                    "duplicate_rate": (
                        row.duplicate_count / row.accepted_canonical_count
                        if row.accepted_canonical_count
                        else 0.0
                    ),
                    "timeout_rate": (
                        row.timeout_count / row.request_count if row.request_count else 0.0
                    ),
                    "rate_limit_rate": (
                        row.rate_limit_count / row.request_count if row.request_count else 0.0
                    ),
                    "average_latency_ms": (
                        row.latency_total_ms / row.request_count if row.request_count else 0.0
                    ),
                }
                for row in rows
            }

    def clear_cache(self) -> int:
        with self.session_factory() as db:
            result = db.execute(delete(DiscoveryCache))
            db.commit()
            return int(result.rowcount or 0)
