import asyncio

from scripts.evidence_gap_benchmark import (
    measure_first_useful_result,
    measure_gdelt_budget,
)


def test_gdelt_retry_loop_stays_inside_one_total_budget_and_opens_circuit() -> None:
    evidence = asyncio.run(measure_gdelt_budget())

    assert len(evidence["searches"]) == 2
    for search in evidence["searches"]:
        assert search["attempt_count"] == 2
        assert len(search["attempt_durations_ms"]) == 2
        assert 150 <= search["retry_backoff_ms"] <= 330
        assert search["total_wall_clock_ms"] < (search["configured_total_budget_ms"] + 100)
    assert evidence["searches"][0]["circuit_breaker_state"] == "closed"
    assert evidence["searches"][1]["circuit_breaker_state"] == "open"
    assert evidence["open_circuit_response"]["error_category"] == "circuit_open"
    assert evidence["open_circuit_response"]["attempt_count"] == 0
    assert evidence["open_circuit_response"]["wall_clock_ms"] < 25


def test_first_useful_source_finishes_while_slow_failure_is_isolated() -> None:
    evidence = asyncio.run(measure_first_useful_result())

    assert evidence["first_useful_source_completion_ms"] < 100
    assert evidence["source_completion_ms"]["slow"] >= 150
    assert evidence["total_search_completion_ms"] < 500
    assert evidence["incremental_results_exposed"] is False
    assert evidence["session_status"] == "partial"
    assert evidence["result_count"] == 2
    assert evidence["warning_sources"] == ["slow"]
