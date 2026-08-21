from __future__ import annotations

import asyncio
from time import perf_counter

import httpx
import pytest

from mirsad_api.connectors import (
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorSearchOptions,
    GdeltConnector,
    GitHubConnector,
    HackerNewsConnector,
    MockConnector,
    RssConnector,
)


@pytest.mark.asyncio
async def test_connector_diagnostics_are_isolated_between_async_search_contexts() -> None:
    connector = MockConnector()
    ready = asyncio.Event()

    async def operation(count: int) -> int:
        connector.last_diagnostics = ConnectorDiagnostics(raw_result_count=count)
        if count == 1:
            ready.set()
            await asyncio.sleep(0.02)
        else:
            await ready.wait()
        return connector.last_diagnostics.raw_result_count

    assert await asyncio.gather(operation(1), operation(2)) == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "http_401"),
        (403, "http_403"),
        (404, "http_404"),
        (429, "rate_limited"),
        (503, "upstream_5xx"),
    ],
)
async def test_http_failures_are_classified(status: int, code: str) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"message": "safe fixture"})

    connector = HackerNewsConnector(retries=1, transport=httpx.MockTransport(handler), timeout=0.1)
    with pytest.raises(ConnectorError) as raised:
        await connector.search("test", limit=1)
    assert raised.value.code == code
    assert raised.value.status_code == status
    assert calls == (2 if status in {429, 503} else 1)


@pytest.mark.asyncio
async def test_timeout_is_classified_and_retry_is_bounded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("fixture timeout", request=request)

    connector = HackerNewsConnector(retries=2, transport=httpx.MockTransport(handler), timeout=0.01)
    with pytest.raises(ConnectorError) as raised:
        await connector.search("test", limit=1)
    assert raised.value.code == "timeout"
    assert calls == 3


def test_github_issue_and_pull_request_normalization() -> None:
    connector = GitHubConnector(scopes=["issues", "pull_requests"])
    payload = {
        "id": 99,
        "number": 7,
        "title": "Institutional issue",
        "body": "Original issue body",
        "html_url": "https://github.com/org/repo/issues/7",
        "repository_url": "https://api.github.com/repos/org/repo",
        "user": {"login": "analyst"},
        "comments": 4,
        "reactions": {"total_count": 3},
        "_mirsad_type": "issues",
    }
    issue = connector.normalize(payload)
    pull = connector.normalize(
        {
            **payload,
            "id": 100,
            "html_url": "https://github.com/org/repo/pull/7",
            "_mirsad_type": "pull_requests",
        }
    )
    assert issue.raw_metadata["source_type"] == "issue"
    assert pull.raw_metadata["source_type"] == "pull_request"
    assert issue.raw_metadata["repository"] == "org/repo"


@pytest.mark.asyncio
async def test_mock_external_ids_are_stable_per_query_and_distinct_between_queries() -> None:
    connector = MockConnector()
    first = await connector.search("public policy", limit=1)
    repeated = await connector.search("public policy", limit=1)
    other = await connector.search("وزارة الصحة", limit=1)

    assert first[0].external_id == repeated[0].external_id
    assert first[0].external_id != other[0].external_id


@pytest.mark.asyncio
async def test_github_retains_successful_scope_and_reports_partial_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "is:issue" in request.url.params["q"]:
            return httpx.Response(403, json={"message": "fixture restriction"})
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 1,
                        "full_name": "org/project",
                        "html_url": "https://github.com/org/project",
                        "owner": {"login": "org"},
                    }
                ]
            },
        )

    connector = GitHubConnector(
        scopes=["repositories", "issues"],
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search("project", limit=10)
    assert [item.raw_metadata["source_type"] for item in items] == ["repository"]
    assert connector.last_diagnostics.warning_code == "http_403"
    assert connector.last_diagnostics.warning_status_code == 403


@pytest.mark.asyncio
async def test_github_health_probe_recovers_and_classifies_external_403() -> None:
    healthy = GitHubConnector(
        retries=0,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"resources": {}})),
    )
    assert (await healthy.health_check())["status"] == "healthy"

    limited = GitHubConnector(
        retries=0,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(403, json={"message": "rate limit"})
        ),
    )
    assert (await limited.health_check())["status"] == "external_limit"


@pytest.mark.asyncio
async def test_rss_preserves_rate_limit_and_invalid_payload_categories() -> None:
    limited = RssConnector(
        retries=0,
        transport=httpx.MockTransport(lambda _request: httpx.Response(429)),
    )
    with pytest.raises(ConnectorError) as rate_limit:
        await limited.search("policy", limit=1)
    assert rate_limit.value.code == "rate_limited"

    invalid = RssConnector(
        retries=0,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not xml")),
    )
    with pytest.raises(ConnectorError) as invalid_payload:
        await invalid.search("policy", limit=1)
    assert invalid_payload.value.code == "invalid_payload"


@pytest.mark.asyncio
async def test_rss_normalizes_valid_rss_links() -> None:
    document = """<?xml version="1.0"?>
    <rss><channel><item>
      <guid>fixture-1</guid>
      <link>https://news.example/public-policy</link>
      <title>Public policy briefing</title>
      <description>Institutional analysis</description>
      <pubDate>Sat, 08 Aug 2026 00:00:00 GMT</pubDate>
    </item></channel></rss>"""
    connector = RssConnector(
        retries=0,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text=document)),
    )

    items = await connector.search("public policy", limit=1)

    assert items[0].canonical_url == "https://news.example/public-policy"
    assert connector.last_diagnostics.raw_result_count == 1
    assert connector.last_diagnostics.malformed_count == 0
    assert connector.last_diagnostics.attempt_count == 1
    assert len(connector.last_diagnostics.attempt_latencies_ms) == 1


@pytest.mark.asyncio
async def test_rss_reports_each_filter_stage_and_strips_html() -> None:
    document = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <guid>matching</guid>
        <link>https://news.example/public-policy</link>
        <title>Public policy briefing</title>
        <description><![CDATA[<p>Institutional <strong>analysis</strong></p>]]></description>
      </item>
      <item>
        <guid>not-matching</guid>
        <link>https://news.example/sports</link>
        <title>Sports briefing</title>
        <description>Match report</description>
      </item>
      <item>
        <guid>invalid-url</guid>
        <link></link>
        <title>Public policy without a URL</title>
      </item>
    </channel></rss>"""
    connector = RssConnector(
        retries=0,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text=document)),
    )

    items = await connector.search_with_options(
        "policy public",
        limit=10,
        options=ConnectorSearchOptions(exact_phrase=False),
    )

    assert [item.external_id for item in items] == ["matching"]
    assert items[0].text == "Institutional analysis"
    assert items[0].raw_metadata["original_description"].startswith("<p>")
    diagnostics = connector.last_diagnostics
    assert diagnostics.fetched_result_count == 3
    assert diagnostics.schema_valid_count == 2
    assert diagnostics.query_match_count == 1
    assert diagnostics.time_eligible_count == 1
    assert diagnostics.normalized_result_count == 1
    assert diagnostics.malformed_count == 1
    assert diagnostics.query_excluded_count == 1

    exact = await connector.search_with_options(
        "policy public",
        limit=10,
        options=ConnectorSearchOptions(exact_phrase=True),
    )
    assert exact == []
    assert connector.last_diagnostics.fetched_result_count == 3
    assert connector.last_diagnostics.schema_valid_count == 2
    assert connector.last_diagnostics.query_match_count == 0


@pytest.mark.asyncio
async def test_rss_partial_feed_failure_is_visible_without_losing_results() -> None:
    document = """<rss><channel><item><guid>1</guid>
    <link>https://news.example/policy</link><title>Public policy</title>
    </item></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "failed.example":
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request, text=document)

    connector = RssConnector(
        feed_urls=["https://news.example/feed", "https://failed.example/feed"],
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search("public policy", limit=10)
    assert len(items) == 1
    assert connector.last_diagnostics.warning_code == "upstream_5xx"
    assert connector.last_diagnostics.attempt_count == 2


@pytest.mark.asyncio
async def test_gdelt_total_budget_and_timeout_circuit_breaker_are_bounded() -> None:
    async def slow_response(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.5)
        return httpx.Response(200, json={"articles": []})

    connector = GdeltConnector(
        timeout=1,
        retries=2,
        total_budget_seconds=0.05,
        circuit_failure_threshold=1,
        circuit_cooldown_seconds=10,
        transport=httpx.MockTransport(slow_response),
    )
    started = perf_counter()
    with pytest.raises(ConnectorError) as first_error:
        await connector.search("public policy", limit=10)
    first_elapsed = perf_counter() - started

    assert first_error.value.code == "timeout"
    assert first_elapsed < 0.4
    assert connector.last_diagnostics.attempt_count == 1
    assert len(connector.last_diagnostics.attempt_latencies_ms) == 1
    assert connector.last_diagnostics.total_latency_ms < 400
    assert connector.last_diagnostics.circuit_breaker_state == "open"

    started = perf_counter()
    with pytest.raises(ConnectorError) as circuit_error:
        await connector.search("open data", limit=10)
    assert circuit_error.value.code == "circuit_open"
    assert perf_counter() - started < 0.02
    assert connector.last_diagnostics.attempt_count == 0
    assert connector.last_diagnostics.circuit_breaker_state == "open"


@pytest.mark.asyncio
async def test_gdelt_repeated_transient_network_failures_open_circuit() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("fixture network unavailable", request=request)

    connector = GdeltConnector(
        timeout=0.1,
        retries=0,
        total_budget_seconds=0.2,
        circuit_failure_threshold=2,
        circuit_cooldown_seconds=10,
        transport=httpx.MockTransport(unavailable),
    )

    for expected_state in ("closed", "open"):
        with pytest.raises(ConnectorError) as error:
            await connector.search("public policy", limit=10)
        assert error.value.code == "dns_network"
        assert connector.last_diagnostics.circuit_breaker_state == expected_state

    started = perf_counter()
    with pytest.raises(ConnectorError) as circuit_error:
        await connector.search("open data", limit=10)
    assert circuit_error.value.code == "circuit_open"
    assert perf_counter() - started < 0.02
    assert connector.last_diagnostics.attempt_count == 0
