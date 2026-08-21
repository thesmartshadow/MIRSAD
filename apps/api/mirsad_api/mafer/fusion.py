from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveryRankObservation:
    canonical_url: str
    engine: str
    variant_id: str
    rank: int
    engine_weight: float = 1.0
    variant_confidence: float = 1.0
    round_number: int = 1


@dataclass(frozen=True, slots=True)
class FusedDiscoveryScore:
    canonical_url: str
    score: float
    engines: tuple[str, ...]
    variants: tuple[str, ...]
    rounds: tuple[int, ...]
    independent_support: int


def weighted_reciprocal_rank_fusion(
    observations: Iterable[DiscoveryRankObservation], *, k: int = 60
) -> tuple[FusedDiscoveryScore, ...]:
    """Fuse incompatible discovery rankings; raw upstream scores are never compared."""

    denominator = max(1, min(k, 1000))
    values: dict[str, float] = defaultdict(float)
    support: dict[str, set[tuple[str, str, int]]] = defaultdict(set)
    engines: dict[str, set[str]] = defaultdict(set)
    variants: dict[str, set[str]] = defaultdict(set)
    rounds: dict[str, set[int]] = defaultdict(set)
    for item in observations:
        if item.rank < 1 or not item.canonical_url:
            continue
        weight = max(0.0, min(item.engine_weight, 2.0)) * max(
            0.0, min(item.variant_confidence, 1.0)
        )
        key = (item.engine, item.variant_id, item.round_number)
        if key in support[item.canonical_url]:
            continue
        support[item.canonical_url].add(key)
        values[item.canonical_url] += weight / (denominator + item.rank)
        engines[item.canonical_url].add(item.engine)
        variants[item.canonical_url].add(item.variant_id)
        rounds[item.canonical_url].add(item.round_number)
    return tuple(
        FusedDiscoveryScore(
            url,
            round(score, 8),
            tuple(sorted(engines[url])),
            tuple(sorted(variants[url])),
            tuple(sorted(rounds[url])),
            len(support[url]),
        )
        for url, score in sorted(values.items(), key=lambda value: (-value[1], value[0]))
    )
