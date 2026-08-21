from __future__ import annotations

import asyncio

import httpx
import pytest

from mirsad_api.connectors import (
    BlueskyConnector,
    ConnectorError,
    ConnectorSearchOptions,
    MastodonConnector,
)
from mirsad_api.models import SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.search import SearchService


def bluesky_post(identifier: str, text: str, *, language: str = "en") -> dict:
    return {
        "uri": f"at://did:plc:test/app.bsky.feed.post/{identifier}",
        "cid": f"cid-{identifier}",
        "author": {"handle": "observer.example", "displayName": "Observer"},
        "record": {
            "text": text,
            "createdAt": "2026-08-01T10:00:00Z",
            "langs": [language],
        },
    }


def mastodon_status(
    identifier: str,
    text: str,
    *,
    url: str | None = None,
    language: str = "en",
    tags: list[str] | None = None,
) -> dict:
    return {
        "id": identifier,
        "uri": url or f"https://origin.example/@observer/{identifier}",
        "url": url or f"https://origin.example/@observer/{identifier}",
        "created_at": "2026-08-01T10:00:00Z",
        "content": f"<p>{text}</p>",
        "language": language,
        "visibility": "public",
        "account": {"display_name": "Observer", "acct": "observer@origin.example"},
        "tags": [{"name": tag} for tag in tags or []],
    }


@pytest.mark.asyncio
async def test_bluesky_primary_appview_returns_arabic_result() -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        return httpx.Response(
            200,
            request=request,
            json={"posts": [bluesky_post("arabic", "بغداد الآن", language="ar")]},
        )

    connector = BlueskyConnector(retries=0, transport=httpx.MockTransport(handler))
    items = await connector.search("بغداد", limit=1)

    assert requested_hosts == ["api.bsky.app"]
    assert items[0].text == "بغداد الآن"
    assert items[0].language == "ar"
    assert connector.last_diagnostics.details["endpoint"] == "https://api.bsky.app"


@pytest.mark.asyncio
async def test_bluesky_primary_403_falls_back_once_without_repeating_forbidden_host() -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "api.bsky.app":
            return httpx.Response(403, request=request, json={"error": "forbidden"})
        return httpx.Response(
            200,
            request=request,
            json={"posts": [bluesky_post("fallback", "open source")]},
        )

    connector = BlueskyConnector(retries=2, transport=httpx.MockTransport(handler))
    items = await connector.search("open source", limit=1)

    assert len(items) == 1
    assert requested_hosts == ["api.bsky.app", "public.api.bsky.app"]
    assert connector.last_diagnostics.details["primary_endpoint_error"] == "http_403"


@pytest.mark.asyncio
async def test_bluesky_rate_limit_is_classified_without_endpoint_hopping() -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        return httpx.Response(429, request=request, json={"error": "limited"})

    connector = BlueskyConnector(retries=0, transport=httpx.MockTransport(handler))
    with pytest.raises(ConnectorError) as error:
        await connector.search("technology", limit=1)

    assert error.value.code == "rate_limited"
    assert requested_hosts == ["api.bsky.app"]


@pytest.mark.asyncio
async def test_bluesky_malformed_posts_payload_is_rejected() -> None:
    connector = BlueskyConnector(
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json={"posts": {}})
        ),
    )

    with pytest.raises(ConnectorError) as error:
        await connector.search("technology", limit=1)

    assert error.value.code == "invalid_payload"


@pytest.mark.asyncio
async def test_bluesky_cursor_pagination_is_bounded_and_preserves_endpoint() -> None:
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        cursors.append(cursor)
        payload = (
            {"posts": [bluesky_post("one", "technology one")], "cursor": "next"}
            if cursor is None
            else {"posts": [bluesky_post("two", "technology two")]}
        )
        return httpx.Response(200, request=request, json=payload)

    connector = BlueskyConnector(retries=0, transport=httpx.MockTransport(handler))
    items = await connector.search("technology", limit=2)

    assert [item.external_id.rsplit("/", 1)[-1] for item in items] == ["one", "two"]
    assert cursors == [None, "next"]


@pytest.mark.asyncio
async def test_bluesky_later_page_403_falls_back_without_repeating_primary() -> None:
    requests: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        cursor = request.url.params.get("cursor")
        requests.append((host, cursor))
        if cursor is None:
            return httpx.Response(
                200,
                request=request,
                json={
                    "posts": [bluesky_post("one", "technology one")],
                    "cursor": "next",
                },
            )
        if host == "api.bsky.app":
            return httpx.Response(403, request=request, json={"error": "forbidden"})
        return httpx.Response(
            200,
            request=request,
            json={"posts": [bluesky_post("two", "technology two")]},
        )

    connector = BlueskyConnector(retries=2, transport=httpx.MockTransport(handler))
    items = await connector.search("technology", limit=2)

    assert [item.external_id.rsplit("/", 1)[-1] for item in items] == ["one", "two"]
    assert requests == [
        ("api.bsky.app", None),
        ("api.bsky.app", "next"),
        ("public.api.bsky.app", "next"),
    ]
    assert connector.last_diagnostics.details["primary_endpoint_error"] == "http_403"


@pytest.mark.asyncio
async def test_bluesky_later_page_failure_preserves_successful_first_page() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.host)
        if request.url.params.get("cursor") is None:
            return httpx.Response(
                200,
                request=request,
                json={
                    "posts": [bluesky_post("one", "technology one")],
                    "cursor": "next",
                },
            )
        return httpx.Response(403, request=request, json={"error": "forbidden"})

    connector = BlueskyConnector(retries=2, transport=httpx.MockTransport(handler))
    items = await connector.search("technology", limit=2)

    assert [item.external_id.rsplit("/", 1)[-1] for item in items] == ["one"]
    assert requests == ["api.bsky.app", "api.bsky.app", "public.api.bsky.app"]
    assert connector.last_diagnostics.warning_code == "http_403"
    assert connector.last_diagnostics.details["partial_page_failure"] == "http_403"


@pytest.mark.asyncio
async def test_mastodon_public_timeline_filters_english_and_reports_stages() -> None:
    payload = [
        mastodon_status("matching", "Open source technology update"),
        mastodon_status("excluded", "Local community gardening"),
    ]
    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json=payload)
        ),
    )

    items = await connector.search("open source", limit=10)

    assert [item.external_id for item in items] == [payload[0]["uri"]]
    diagnostics = connector.last_diagnostics
    assert diagnostics.fetched_result_count == 2
    assert diagnostics.schema_valid_count == 2
    assert diagnostics.query_match_count == 1
    assert diagnostics.normalized_result_count == 1
    assert diagnostics.details["mode"] == "PUBLIC_TIMELINE"
    assert diagnostics.details["local_query_matches"] == 1


@pytest.mark.asyncio
async def test_mastodon_public_preview_401_is_auth_required_not_connector_defect() -> None:
    connector = MastodonConnector(
        public_instances=["https://private-preview.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, request=request, json={"error": "auth"})
        ),
    )

    validation = await connector.validate_access()
    assert validation.state == "warn"
    assert validation.code == "auth_required"
    assert connector.last_diagnostics.details["instance_results"][0]["state"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_mastodon_public_timeline_timeout_is_isolated_and_classified() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    connector = MastodonConnector(
        public_instances=["https://slow.example"],
        retries=0,
        transport=httpx.MockTransport(timeout),
    )

    with pytest.raises(ConnectorError) as error:
        await connector.search("technology", limit=10)
    assert error.value.code == "timeout"


@pytest.mark.asyncio
async def test_mastodon_malformed_public_records_are_counted() -> None:
    payload = ["not-an-object", {"id": "missing-content-and-url"}]
    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json=payload)
        ),
    )

    assert await connector.search("technology", limit=10) == []
    assert connector.last_diagnostics.fetched_result_count == 2
    assert connector.last_diagnostics.schema_valid_count == 0
    assert connector.last_diagnostics.malformed_count == 2


@pytest.mark.asyncio
async def test_mastodon_public_timeline_matches_arabic_normalized_text() -> None:
    payload = [mastodon_status("ar", "أخبار بَغْدَاد الآن", language="ar")]
    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json=payload)
        ),
    )

    items = await connector.search("بغداد", limit=10)
    assert len(items) == 1
    assert items[0].text == "أخبار بَغْدَاد الآن"


@pytest.mark.asyncio
async def test_mastodon_public_timeline_can_return_a_valid_zero_match() -> None:
    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                request=request,
                json=[mastodon_status("one", "Community gardening")],
            )
        ),
    )

    assert await connector.search("technology", limit=10) == []
    assert connector.last_diagnostics.fetched_result_count == 1
    assert connector.last_diagnostics.query_match_count == 0


@pytest.mark.asyncio
async def test_mastodon_hashtag_query_uses_documented_tag_timeline() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(
            200,
            request=request,
            json=[mastodon_status("tag", "Update", tags=["technology"])],
        )

    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search_with_options(
        "#technology",
        limit=10,
        options=ConnectorSearchOptions(),
    )

    assert len(items) == 1
    assert paths == ["/api/v1/timelines/tag/technology"]
    assert connector.last_diagnostics.details["mode"] == "HASHTAG_TIMELINE"


@pytest.mark.asyncio
async def test_mastodon_federated_duplicate_preserves_instance_provenance() -> None:
    shared_url = "https://origin.example/@observer/shared"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=[mastodon_status(request.url.host, "Technology report", url=shared_url)],
        )

    connector = MastodonConnector(
        public_instances=["https://one.example", "https://two.example"],
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search("technology", limit=10)

    assert len(items) == 1
    assert set(items[0].raw_metadata["observed_instances"]) == {
        "https://one.example",
        "https://two.example",
    }
    assert connector.last_diagnostics.details["duplicates"] == 1


@pytest.mark.asyncio
async def test_mastodon_multi_instance_failure_does_not_discard_healthy_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "failed.example":
            return httpx.Response(503, request=request, json={"error": "down"})
        return httpx.Response(
            200,
            request=request,
            json=[mastodon_status("healthy", "Technology report")],
        )

    connector = MastodonConnector(
        public_instances=["https://failed.example", "https://healthy.example"],
        retries=0,
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search("technology", limit=10)

    assert len(items) == 1
    assert connector.last_diagnostics.warning_code == "upstream_5xx"
    states = {
        result["instance"]: result["state"]
        for result in connector.last_diagnostics.details["instance_results"]
    }
    assert states == {
        "https://failed.example": "UNAVAILABLE",
        "https://healthy.example": "PUBLIC_TIMELINE_AVAILABLE",
    }


@pytest.mark.asyncio
async def test_mastodon_public_instances_are_requested_concurrently() -> None:
    both_started = asyncio.Event()
    started = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.2)
        return httpx.Response(200, request=request, json=[])

    connector = MastodonConnector(
        public_instances=["https://one.example", "https://two.example"],
        retries=0,
        transport=httpx.MockTransport(handler),
    )

    assert await connector.search("technology", limit=10) == []
    assert started == 2


@pytest.mark.asyncio
async def test_mastodon_public_stage_counts_reach_search_diagnostics(db, settings) -> None:
    connector = MastodonConnector(
        public_instances=["https://social.example"],
        retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                request=request,
                json=[mastodon_status("one", "Technology public update")],
            )
        ),
    )
    connectors = {"mastodon": connector}
    seed_database(db, connectors)

    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="technology", sources=["mastodon"], time_range="all", limit=10)
    )
    connector_diagnostics = db.get(SearchSession, session_id).diagnostics["connectors"][0]

    assert connector_diagnostics["mode"] == "PUBLIC_TIMELINE"
    assert connector_diagnostics["fetched_results"] == 1
    assert connector_diagnostics["schema_valid_results"] == 1
    assert connector_diagnostics["local_query_matches"] == 1
    assert connector_diagnostics["normalized_results"] == 1
    assert connector_diagnostics["duplicates"] == 0
    assert connector_diagnostics["instance_results"][0]["instance"] == (
        "https://social.example"
    )
