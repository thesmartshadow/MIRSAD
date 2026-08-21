from __future__ import annotations

from dataclasses import dataclass

from ..connectors.base import ConnectorItem


@dataclass(frozen=True, slots=True)
class EvidenceCompleteness:
    level: str
    score: float
    available: tuple[str, ...]
    missing: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "score": round(self.score, 3),
            "available": list(self.available),
            "missing": list(self.missing),
        }


def evidence_completeness(item: ConnectorItem) -> EvidenceCompleteness:
    checks = {
        "canonical_url": bool(item.canonical_url),
        "indexed_title": bool(item.title),
        "indexed_snippet": bool(item.text),
        "full_text": bool(item.raw_metadata.get("full_text"))
        or (not item.raw_metadata.get("indexed_public_web_coverage") and len(item.text) >= 80),
        "author": bool(item.author or item.author_handle),
        "published_timestamp": item.published_at is not None,
        "official_embed_metadata": bool(item.raw_metadata.get("enrichment_metadata")),
    }
    weights = {
        "canonical_url": 0.16,
        "indexed_title": 0.12,
        "indexed_snippet": 0.18,
        "full_text": 0.22,
        "author": 0.1,
        "published_timestamp": 0.12,
        "official_embed_metadata": 0.1,
    }
    score = sum(weights[key] for key, present in checks.items() if present)
    if score >= 0.75:
        level = "RICH"
    elif score >= 0.45:
        level = "MODERATE"
    else:
        level = "SPARSE"
    return EvidenceCompleteness(
        level,
        score,
        tuple(key for key, present in checks.items() if present),
        tuple(key for key, present in checks.items() if not present),
    )
