from __future__ import annotations

import asyncio

import httpx
import pytest
from scripts.verify_sources import verify_one

from mirsad_api.connectors import (
    BlueskyConnector,
    MastodonConnector,
    MockConnector,
    XConnector,
    YouTubeConnector,
)


@pytest.mark.asyncio
async def test_unconfigured_optional_source_is_warning_without_network() -> None:
    result = await verify_one(YouTubeConnector())

    assert result["state"] == "warn"
    assert result["code"] == "unconfigured"
    assert result["request_performed"] is False
    assert result["internal_failure"] is False


@pytest.mark.asyncio
async def test_authentication_rejection_is_a_safe_non_internal_failure() -> None:
    connector = XConnector(
        bearer_token="never-report-this-token",
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, request=request, json={"error": "rejected"})
        ),
    )

    result = await verify_one(connector)

    assert result["state"] == "fail"
    assert result["code"] == "http_401"
    assert result["message"] == "Authentication rejected"
    assert result["internal_failure"] is False
    assert "never-report-this-token" not in str(result)


@pytest.mark.asyncio
async def test_credential_free_forbidden_source_is_not_described_as_authenticated() -> None:
    connector = BlueskyConnector(
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(403, request=request, json={"error": "forbidden"})
        ),
    )

    result = await verify_one(connector)

    assert result["state"] == "fail"
    assert result["code"] == "http_403"
    assert result["message"] == "Public endpoint access was forbidden from this environment"
    assert "credential" not in result["message"].casefold()


@pytest.mark.asyncio
async def test_bluesky_verification_probes_the_real_search_endpoint() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.url.params["q"] == "open source"
        assert request.url.params["limit"] == "1"
        return httpx.Response(200, request=request, json={"posts": []})

    result = await verify_one(
        BlueskyConnector(retries=0, transport=httpx.MockTransport(handler))
    )

    assert result["state"] == "pass"
    assert result["message"] == "Public AppView search available"
    assert paths == ["/xrpc/app.bsky.feed.searchPosts"]


@pytest.mark.asyncio
async def test_mastodon_public_mode_verifies_without_credentials() -> None:
    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json=[])
        ),
    )

    result = await verify_one(connector)

    assert result["state"] == "pass"
    assert result["configured"] is True
    assert result["message"] == "Public timeline mode; full-text search not configured"
    assert result["http_status"] == 200


@pytest.mark.asyncio
async def test_youtube_health_uses_the_minimal_credential_probe() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"items": []})

    connector = YouTubeConnector(
        api_key="fixture-key",
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    health = await connector.health_check()

    assert health["status"] == "healthy"
    assert health["detail"] == "API key accepted by YouTube Data API"
    assert requests[0].url.path == "/youtube/v3/i18nLanguages"
    assert requests[0].headers["X-Goog-Api-Key"] == "fixture-key"


@pytest.mark.asyncio
async def test_successful_access_check_records_request_and_latency() -> None:
    connector = XConnector(
        bearer_token="secret",
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json={"data": []})
        ),
    )

    result = await verify_one(connector)

    assert result["state"] == "pass"
    assert result["request_performed"] is True
    assert result["attempt_count"] == 1
    assert result["http_status"] == 200


@pytest.mark.asyncio
async def test_source_validation_has_an_outer_time_budget() -> None:
    connector = MockConnector()

    async def slow_validation():
        await asyncio.sleep(0.2)

    connector.validate_access = slow_validation  # type: ignore[method-assign]
    result = await verify_one(connector, timeout_seconds=0.01)
    assert result["code"] == "timeout"
    assert result["internal_failure"] is False
