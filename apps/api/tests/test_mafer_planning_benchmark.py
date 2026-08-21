from __future__ import annotations

from scripts.evaluate_mafer_planning import evaluate


def test_phase2_planning_benchmark_is_deterministic_and_measures_tradeoffs() -> None:
    first = evaluate()
    second = evaluate()

    assert first["fixture_sha256"] == second["fixture_sha256"]
    assert first["queries"] == second["queries"] == 20
    assert first["strategies"] == second["strategies"]
    assert first["modes"] == second["modes"]
    assert first["segments"] == second["segments"]
    assert first["cases"] == second["cases"]

    baseline = first["strategies"]["BASELINE"]
    final = first["strategies"]["+ Gated evidence expansion"]
    assert final["p_at_5"] > baseline["p_at_5"]
    assert final["candidate_recall"] >= baseline["candidate_recall"]
    assert final["unique_useful_urls"] > baseline["unique_useful_urls"]

    fast = first["modes"]["fast"]
    balanced = first["modes"]["balanced"]
    deep = first["modes"]["deep"]
    assert fast["requests_per_query"] < balanced["requests_per_query"]
    assert fast["latency_per_query_ms"] < balanced["latency_per_query_ms"]
    assert deep["candidate_recall"] >= balanced["candidate_recall"]
    assert first["segments"]["language"]["arabic"]["queries"] >= 5
    assert first["segments"]["language"]["mixed"]["queries"] >= 2
