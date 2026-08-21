from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..domains.query import normalize_text
from ..models import EntityAliasEdge


@dataclass(frozen=True, slots=True)
class AliasEvidence:
    value: str
    relationship_type: str
    support_count: int
    confidence: float
    evidence_sources: tuple[str, ...]


class EntityAliasRepository:
    """Conservative evidence graph; similarity alone never creates an identity edge."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def aliases_for(
        self, value: str, *, minimum_confidence: float = 0.8
    ) -> tuple[AliasEvidence, ...]:
        normalized = normalize_text(value)
        rows = self.db.scalars(
            select(EntityAliasEdge)
            .where(
                or_(
                    EntityAliasEdge.left_normalized == normalized,
                    EntityAliasEdge.right_normalized == normalized,
                ),
                EntityAliasEdge.confidence >= minimum_confidence,
                EntityAliasEdge.support_count >= 2,
            )
            .order_by(EntityAliasEdge.confidence.desc(), EntityAliasEdge.right_value)
            .limit(5)
        ).all()
        output: list[AliasEvidence] = []
        for row in rows:
            alias = row.right_value if row.left_normalized == normalized else row.left_value
            output.append(
                AliasEvidence(
                    alias,
                    row.relationship_type,
                    row.support_count,
                    row.confidence,
                    tuple(row.evidence_sources or ()),
                )
            )
        return tuple(output)

    def observe(
        self,
        left: str,
        right: str,
        *,
        relationship_type: str,
        evidence_source: str,
        direct_evidence: bool = False,
    ) -> EntityAliasEdge | None:
        left_clean = left.strip()
        right_clean = right.strip()
        left_normalized = normalize_text(left_clean)
        right_normalized = normalize_text(right_clean)
        if (
            not left_normalized
            or not right_normalized
            or left_normalized == right_normalized
            or len(left_normalized) > 300
            or len(right_normalized) > 500
        ):
            return None
        row = self.db.scalar(
            select(EntityAliasEdge).where(
                EntityAliasEdge.left_normalized == left_normalized,
                EntityAliasEdge.right_normalized == right_normalized,
                EntityAliasEdge.relationship_type == relationship_type,
            )
        )
        if row is None:
            row = EntityAliasEdge(
                left_value=left_clean,
                left_normalized=left_normalized,
                right_value=right_clean,
                right_normalized=right_normalized,
                relationship_type=relationship_type,
                evidence_sources=[evidence_source],
                support_count=1,
                confidence=0.8 if direct_evidence else 0.55,
            )
            self.db.add(row)
            # Search sessions use autoflush=False; make this edge visible to a
            # second independent observation in the same collection round.
            self.db.flush()
            return row
        sources = set(row.evidence_sources or ())
        is_independent = evidence_source not in sources
        sources.add(evidence_source)
        if is_independent:
            row.support_count += 1
        row.evidence_sources = sorted(sources)
        row.confidence = min(
            0.98,
            max(row.confidence, 0.8 if direct_evidence else 0.55)
            + (0.1 if is_independent else 0.0),
        )
        row.last_seen_at = datetime.now(UTC)
        self.db.flush()
        return row
