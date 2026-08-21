from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import AlgorithmConfigurationSnapshot
from .versions import production_versions, shadow_versions

VERIFIED_PRODUCTION = "verified_production"
EXPERIMENTAL = "experimental"
PROMOTION_CANDIDATE = "promotion_candidate"
PREVIOUS_PRODUCTION = "previous_production"
DEFAULT_BENCHMARK_HASHES = {
    "mafer_phase2": "56adbd8be2e77991d0258b9be0ac5da0cf5b134fa5ec748e311187b2f5153f2e",
    "mafer_phase3_development": (
        "cf5be21e8d87e57599787a12472a0358fc59a67c850dd1f4dc84758c441ebae8"
    ),
    "mafer_phase3_holdout": ("50b06e990e39e41995893b4de288553d16d4f575ca2d825554039004b23b5ca2"),
}


def ensure_configuration_snapshots(
    db: Session,
    *,
    benchmark_hashes: dict[str, str] | None = None,
) -> list[AlgorithmConfigurationSnapshot]:
    rows = db.scalars(
        select(AlgorithmConfigurationSnapshot).where(AlgorithmConfigurationSnapshot.active)
    ).all()
    active_slots = {row.slot for row in rows}
    if VERIFIED_PRODUCTION not in active_slots:
        row = AlgorithmConfigurationSnapshot(
            slot=VERIFIED_PRODUCTION,
            configuration=production_versions(),
            benchmark_hashes=benchmark_hashes or DEFAULT_BENCHMARK_HASHES,
            metrics={},
            reason="Verified deterministic Phase-2 production configuration",
        )
        db.add(row)
        rows.append(row)
    if EXPERIMENTAL not in active_slots:
        row = AlgorithmConfigurationSnapshot(
            slot=EXPERIMENTAL,
            configuration={**production_versions(), **shadow_versions()},
            benchmark_hashes=benchmark_hashes or DEFAULT_BENCHMARK_HASHES,
            metrics={},
            reason="Phase-3 shadow configuration; cannot affect user-visible retrieval",
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def active_snapshot(db: Session, slot: str) -> AlgorithmConfigurationSnapshot | None:
    return db.scalar(
        select(AlgorithmConfigurationSnapshot)
        .where(
            AlgorithmConfigurationSnapshot.slot == slot,
            AlgorithmConfigurationSnapshot.active,
        )
        .order_by(AlgorithmConfigurationSnapshot.created_at.desc())
    )


def create_snapshot(
    db: Session,
    *,
    slot: str,
    configuration: dict[str, Any],
    benchmark_hashes: dict[str, str],
    metrics: dict[str, Any],
    reason: str,
) -> AlgorithmConfigurationSnapshot:
    if slot not in {VERIFIED_PRODUCTION, EXPERIMENTAL, PROMOTION_CANDIDATE, PREVIOUS_PRODUCTION}:
        raise ValueError("Unsupported configuration slot")
    db.execute(
        update(AlgorithmConfigurationSnapshot)
        .where(AlgorithmConfigurationSnapshot.slot == slot)
        .values(active=False)
    )
    row = AlgorithmConfigurationSnapshot(
        slot=slot,
        configuration=configuration,
        benchmark_hashes=benchmark_hashes,
        metrics=metrics,
        reason=reason[:500],
        active=True,
    )
    db.add(row)
    db.flush()
    return row


def rollback_one_step(db: Session, *, reason: str) -> AlgorithmConfigurationSnapshot:
    current = active_snapshot(db, VERIFIED_PRODUCTION)
    previous = active_snapshot(db, PREVIOUS_PRODUCTION)
    if current is None or previous is None:
        raise ValueError("No previous production configuration is available")
    create_snapshot(
        db,
        slot=PREVIOUS_PRODUCTION,
        configuration=current.configuration,
        benchmark_hashes=current.benchmark_hashes,
        metrics=current.metrics,
        reason=f"Rollback archive: {reason}",
    )
    return create_snapshot(
        db,
        slot=VERIFIED_PRODUCTION,
        configuration=previous.configuration,
        benchmark_hashes=previous.benchmark_hashes,
        metrics=previous.metrics,
        reason=f"One-step rollback: {reason}",
    )
