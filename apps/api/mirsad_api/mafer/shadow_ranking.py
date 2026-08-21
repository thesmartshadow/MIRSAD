from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intent import IntentLabel, QueryIntentFingerprint
from .versions import SHADOW_DIVERSITY_VERSION, SHADOW_FUSION_VERSION

DEVELOPMENT_DATASET_SHA256 = "cf5be21e8d87e57599787a12472a0358fc59a67c850dd1f4dc84758c441ebae8"
LEXICAL_WEIGHTS = {
    IntentLabel.IDENTIFIER: 0.70,
    IntentLabel.HANDLE: 0.70,
    IntentLabel.HASHTAG: 0.70,
    IntentLabel.EXACT_PHRASE: 0.55,
    IntentLabel.PERSON_LIKE: 0.55,
    IntentLabel.ENTITY_LIKE: 0.70,
}


def query_aware_lexical_weight(fingerprint: QueryIntentFingerprint) -> float:
    return next(
        (weight for label, weight in LEXICAL_WEIGHTS.items() if fingerprint.has(label)),
        0.25,
    )


@dataclass(frozen=True, slots=True)
class ShadowRankedItem:
    key: int
    source: str
    score: float
    story: str


def fusion_order(
    items: list[tuple[int, str, float, float | None]],
    *,
    lexical_weight: float,
) -> list[int]:
    scored = [
        (
            lexical_weight * lexical
            + (1 - lexical_weight) * (semantic if semantic is not None else lexical),
            lexical,
            key,
        )
        for key, _source, lexical, semantic in items
    ]
    return [key for _score, _lexical, key in sorted(scored, reverse=True)]


def near_tie_diversity_order(
    items: list[ShadowRankedItem],
    *,
    maximum_delta: float = 2.0,
    relevance_floor: float = 70.0,
) -> list[int]:
    output: list[ShadowRankedItem] = []
    pending = list(items)
    while pending:
        best = pending.pop(0)
        if output and best.score >= relevance_floor:
            alternative = next(
                (
                    candidate
                    for candidate in pending
                    if candidate.score >= relevance_floor
                    and best.score - candidate.score <= maximum_delta
                    and candidate.story != output[-1].story
                    and candidate.source != output[-1].source
                ),
                None,
            )
            if alternative is not None:
                pending.remove(alternative)
                pending.insert(0, best)
                best = alternative
        output.append(best)
    return [item.key for item in output]


def shadow_ranking_summary(
    *,
    production_order: list[int],
    fusion: list[int],
    diversity: list[int],
    lexical_weight: float,
) -> dict[str, Any]:
    top = min(10, len(production_order))
    production_top = production_order[:top]
    return {
        "mode": "SHADOW_ONLY",
        "development_dataset_sha256": DEVELOPMENT_DATASET_SHA256,
        "fusion": {
            "version": SHADOW_FUSION_VERSION,
            "lexical_weight": lexical_weight,
            "semantic_weight": 1 - lexical_weight,
            "top_10_overlap": len(set(production_top) & set(fusion[:top])),
            "order_changed": fusion != production_order,
            "ordered_keys": fusion,
        },
        "near_tie_diversity": {
            "version": SHADOW_DIVERSITY_VERSION,
            "maximum_score_delta": 2.0,
            "relevance_floor": 70.0,
            "top_10_overlap": len(set(production_top) & set(diversity[:top])),
            "order_changed": diversity != production_order,
            "ordered_keys": diversity,
        },
    }
