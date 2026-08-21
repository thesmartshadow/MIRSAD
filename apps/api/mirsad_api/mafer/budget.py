from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class SearchMode(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


@dataclass(frozen=True, slots=True)
class SearchBudget:
    mode: SearchMode
    max_wall_clock_seconds: float
    max_rounds: int
    max_source_calls: int
    max_discovery_engine_calls: int
    max_query_variants: int
    max_discovered_urls: int
    max_normalized_candidates: int
    max_semantic_candidates: int
    max_historical_calls: int

    def as_dict(self) -> dict[str, object]:
        output = asdict(self)
        output["mode"] = self.mode.value
        return output


BUDGETS = {
    SearchMode.FAST: SearchBudget(SearchMode.FAST, 5.0, 1, 6, 8, 3, 80, 120, 20, 0),
    SearchMode.BALANCED: SearchBudget(SearchMode.BALANCED, 12.0, 2, 12, 20, 6, 200, 300, 20, 0),
    SearchMode.DEEP: SearchBudget(SearchMode.DEEP, 25.0, 3, 20, 36, 10, 400, 600, 20, 2),
}


def budget_for(mode: SearchMode | str) -> SearchBudget:
    return BUDGETS[SearchMode(mode)]
