from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from mirsad_api.config import Settings
from mirsad_api.connectors import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    ConnectorSearchOptions,
    InstagramConnector,
    MastodonConnector,
    RedditConnector,
    TelegramConnector,
    ThreadsConnector,
    TikTokConnector,
    XConnector,
    YouTubeConnector,
    facebook_connector,
    linkedin_connector,
)
from mirsad_api.domains.engagement import normalize_engagement, social_reach
from mirsad_api.routers.sources import list_sources
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import get_search_response
from mirsad_api.services.search import SearchService


def json_response(request: httpx.Request, payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, request=request, json=payload)


@pytest.mark.asyncio
async def test_x_search_paginates_and_normalizes_arabic_social_fields() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        page = len(calls)
        post_id = str(page)
        return json_response(
            request,
            {
                "data": [
                    {
                        "id": post_id,
                        "text": "بغداد #العراق @analyst",
                        "author_id": "u1",
                        "created_at": "2026-08-01T10:00:00Z",
                        "lang": "ar",
                        "public_metrics": {"like_count": 4, "retweet_count": 1},
                        "referenced_tweets": [{"type": "quoted", "id": "quoted-1"}],
                    }
                ],
                "includes": {
                    "users": [{"id": "u1", "name": "محلل", "username": "analyst", "verified": True}]
                },
                "meta": {"next_token": "next"} if page == 1 else {},
            },
        )

    connector = XConnector(bearer_token="secret", transport=httpx.MockTransport(handler))
    items = await connector.search_with_options(
        "بغداد",
        limit=2,
        since=datetime.now(UTC) - timedelta(days=30),
        options=ConnectorSearchOptions(
            exact_phrase=True,
            language="ar",
            source_options={"x": {"sort": "recent", "exclude_reposts": True}},
        ),
    )
    assert len(items) == 2
    assert items[0].author_handle == "analyst"
    assert items[0].author_verified is True
    assert items[0].hashtags == ("العراق",)
    assert items[0].mentions == ("analyst",)
    assert items[0].raw_metrics == {"likes": 4, "reposts": 1}
    assert items[0].raw_metadata["referenced_tweets"][0]["type"] == "quoted"
    assert "next_token=next" in str(calls[1].url)
    assert "%22" in str(calls[0].url) and "lang%3Aar" in str(calls[0].url)
    start_time = datetime.fromisoformat(calls[0].url.params["start_time"].replace("Z", "+00:00"))
    assert start_time > datetime.now(UTC) - timedelta(days=8)
    assert connector.last_diagnostics.attempt_count == 2
    assert len(connector.last_diagnostics.attempt_latencies_ms) == 2


@pytest.mark.asyncio
async def test_threads_search_modes_empty_and_normalization() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(
            request,
            {
                "data": [
                    {
                        "id": "th-1",
                        "username": "observer",
                        "text": "Baghdad #Iraq",
                        "timestamp": "2026-08-01T10:00:00Z",
                        "permalink": "https://www.threads.net/@observer/post/th-1",
                        "media_type": "TEXT_POST",
                        "is_quote_post": True,
                        "quoted_post": {"id": "original"},
                    }
                ]
            },
        )

    connector = ThreadsConnector(access_token="secret", transport=httpx.MockTransport(handler))
    items = await connector.search_with_options(
        "Baghdad",
        limit=10,
        options=ConnectorSearchOptions(
            source_options={"threads": {"mode": "topic_tag", "sort": "recent"}}
        ),
    )
    assert items[0].raw_metadata["is_quote_post"] is True
    assert "search_mode=TAG" in str(requests[0].url)
    assert "search_type=RECENT" in str(requests[0].url)

    empty = ThreadsConnector(
        access_token="secret",
        transport=httpx.MockTransport(lambda request: json_response(request, {"data": []})),
    )
    assert await empty.search("absent", limit=5) == []


@pytest.mark.asyncio
async def test_reddit_oauth_community_search_and_pagination() -> None:
    listing_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal listing_calls
        if request.url.host == "www.reddit.com":
            return json_response(request, {"access_token": "oauth-token"})
        listing_calls += 1
        post_id = f"p{listing_calls}"
        return json_response(
            request,
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": post_id,
                                "title": "Baghdad update",
                                "selftext": "Public community post",
                                "author": "reporter",
                                "created_utc": 1_785_580_800,
                                "score": 12,
                                "num_comments": 3,
                                "subreddit": "iraq",
                                "permalink": f"/r/iraq/comments/{post_id}/story/",
                            }
                        }
                    ],
                    "after": "cursor" if listing_calls == 1 else None,
                }
            },
        )

    connector = RedditConnector(
        client_id="id",
        client_secret="secret",
        user_agent="MIRSAD tests",
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search_with_options(
        "Baghdad",
        limit=2,
        options=ConnectorSearchOptions(
            source_options={"reddit": {"communities": ["iraq"], "sort": "recent"}}
        ),
    )
    assert len(items) == 2
    assert items[0].raw_metadata["subreddit"] == "iraq"
    assert items[0].raw_metrics == {"score": 12, "comments": 3}
    assert listing_calls == 2
    assert connector.last_diagnostics.attempt_count == 3


@pytest.mark.asyncio
async def test_youtube_searches_all_supported_types_and_keeps_missing_metrics_null() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return json_response(
                request,
                {
                    "items": [
                        {
                            "id": {"videoId": "v1"},
                            "snippet": {
                                "title": "بغداد الآن",
                                "description": "فيديو عام #بغداد",
                                "channelTitle": "Channel",
                                "publishedAt": "2026-08-01T10:00:00Z",
                            },
                        },
                        {
                            "id": {"channelId": "c1"},
                            "snippet": {"title": "Baghdad Channel", "description": "Public"},
                        },
                        {
                            "id": {"playlistId": "l1"},
                            "snippet": {"title": "Baghdad playlist", "description": "Public"},
                        },
                    ]
                },
            )
        return json_response(request, {"items": [{"id": "v1", "statistics": {"viewCount": "9"}}]})

    connector = YouTubeConnector(api_key="key", transport=httpx.MockTransport(handler))
    items = await connector.search("Baghdad", limit=10)
    assert [item.raw_metadata["source_type"] for item in items] == [
        "video",
        "channel",
        "playlist",
    ]
    assert items[0].raw_metrics == {"views": 9}
    assert items[1].raw_metrics == {}
    assert connector.last_diagnostics.attempt_count == 2


@pytest.mark.asyncio
async def test_instagram_is_hashtag_only_and_normalizes_permitted_metrics() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return json_response(request, {"data": [{"id": "tag-id"}]})
        return json_response(
            request,
            {
                "data": [
                    {
                        "id": "ig-1",
                        "caption": "بغداد #العراق",
                        "media_type": "IMAGE",
                        "permalink": "https://www.instagram.com/p/ig-1/",
                        "timestamp": "2026-08-01T10:00:00Z",
                        "username": "observer",
                        "like_count": 2,
                    }
                ]
            },
        )

    connector = InstagramConnector(
        access_token="token", user_id="user", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ConnectorError, match="Global public-post") as error:
        await connector.search("Baghdad", limit=5)
    assert error.value.code == "capability_restricted"
    items = await connector.search("#العراق", limit=5)
    assert items[0].hashtags == ("العراق",)
    assert items[0].raw_metrics == {"likes": 2}
    assert connector.last_diagnostics.attempt_count == 2


@pytest.mark.asyncio
async def test_tiktok_research_adapter_and_restricted_state() -> None:
    restricted = TikTokConnector()
    assert restricted.configuration_state() == "restricted"
    with pytest.raises(ConnectorError) as error:
        await restricted.search("Baghdad", limit=5)
    assert error.value.code == "restricted_access"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token/"):
            return json_response(request, {"access_token": "research-token"})
        return json_response(
            request,
            {
                "data": {
                    "videos": [
                        {
                            "id": 9,
                            "video_description": "بغداد",
                            "username": "researcher",
                            "create_time": 1_785_580_800,
                            "region_code": "IQ",
                            "hashtag_names": ["بغداد"],
                            "view_count": 100,
                            "share_count": 2,
                        }
                    ]
                }
            },
        )

    connector = TikTokConnector(
        client_key="key",
        client_secret="secret",
        research_approved=True,
        transport=httpx.MockTransport(handler),
    )
    items = await connector.search("Baghdad", limit=5)
    assert items[0].raw_metrics == {"views": 100, "shares": 2}
    assert items[0].raw_metadata["region"] == "IQ"
    assert connector.last_diagnostics.attempt_count == 2


@pytest.mark.asyncio
async def test_mastodon_instance_search_strips_html_but_preserves_original() -> None:
    payload = {
        "statuses": [
            {
                "id": "m1",
                "url": "https://social.example/@observer/1",
                "created_at": "2026-08-01T10:00:00Z",
                "content": "<p>بغداد <strong>الآن</strong></p>",
                "account": {"display_name": "Observer", "acct": "observer"},
                "favourites_count": 3,
                "tags": [{"name": "بغداد"}],
            }
        ]
    }
    connector = MastodonConnector(
        instance_url="https://social.example",
        access_token="token",
        transport=httpx.MockTransport(lambda request: json_response(request, payload)),
    )
    items = await connector.search("بغداد", limit=5)
    assert items[0].text == "بغداد الآن"
    assert items[0].raw_metadata["content_html"].startswith("<p>")


class FakeTelegramClient:
    def __init__(self, *_args):
        self.disconnected = False

    async def connect(self):
        return None

    async def is_user_authorized(self):
        return True

    async def disconnect(self):
        self.disconnected = True

    async def __call__(self, _request):
        channel = SimpleNamespace(id=7, broadcast=True, username="public_channel", title="Public")
        message = SimpleNamespace(
            id=11,
            peer_id=SimpleNamespace(channel_id=7),
            message="بغداد #العراق",
            date=datetime(2026, 8, 1, tzinfo=UTC),
            views=50,
            forwards=None,
            replies=SimpleNamespace(replies=2),
            reactions=None,
            media=object(),
        )
        private = SimpleNamespace(
            id=12,
            peer_id=SimpleNamespace(channel_id=8),
            message="must not appear",
        )
        return SimpleNamespace(chats=[channel], messages=[message, private])


@pytest.mark.asyncio
async def test_telegram_filters_to_public_channels() -> None:
    connector = TelegramConnector(
        api_id=1,
        api_hash="hash",
        session_string="session",
        client_factory=FakeTelegramClient,
    )
    items = await connector.search("بغداد", limit=5)
    assert len(items) == 1
    assert items[0].canonical_url == "https://t.me/public_channel/11"
    assert items[0].raw_metadata["coverage"] == "public_channels"
    assert items[0].raw_metrics == {"views": 50, "replies": 2}


@pytest.mark.asyncio
async def test_telegram_has_a_whole_operation_timeout() -> None:
    class SlowTelegramClient(FakeTelegramClient):
        async def connect(self):
            await asyncio.sleep(0.05)

    connector = TelegramConnector(
        api_id=1,
        api_hash="hash",
        session_string="session",
        client_factory=SlowTelegramClient,
        timeout=0.01,
    )
    with pytest.raises(ConnectorError) as error:
        await connector.search("Baghdad", limit=5)
    assert error.value.code == "timeout"


@pytest.mark.asyncio
async def test_social_failures_are_classified_and_malformed_records_are_counted() -> None:
    limited = XConnector(
        bearer_token="token",
        retries=0,
        transport=httpx.MockTransport(
            lambda request: json_response(request, {"error": "limited"}, 429)
        ),
    )
    with pytest.raises(ConnectorError) as rate_error:
        await limited.search("Baghdad", limit=5)
    assert rate_error.value.code == "rate_limited"

    unauthorized = ThreadsConnector(
        access_token="token",
        retries=0,
        transport=httpx.MockTransport(
            lambda request: json_response(request, {"error": "auth"}, 401)
        ),
    )
    with pytest.raises(ConnectorError) as auth_error:
        await unauthorized.search("Baghdad", limit=5)
    assert auth_error.value.code == "http_401"

    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout")

    timed_out = MastodonConnector(
        instance_url="https://social.example",
        access_token="token",
        retries=0,
        transport=httpx.MockTransport(timeout),
    )
    with pytest.raises(ConnectorError) as timeout_error:
        await timed_out.search("Baghdad", limit=5)
    assert timeout_error.value.code == "timeout"

    malformed = XConnector(bearer_token="token")
    assert malformed.normalize_payloads([{"text": "missing identifier"}]) == []
    assert malformed.last_diagnostics.malformed_count == 1


def test_restricted_global_search_and_platform_specific_reach() -> None:
    facebook = facebook_connector()
    linkedin = linkedin_connector()
    assert facebook.configuration_state() == "restricted"
    assert linkedin.configuration_state() == "restricted"
    assert facebook.metadata.capabilities.keyword_search is False
    assert linkedin.metadata.capabilities.keyword_search is False
    assert normalize_engagement("reddit", {"score": 500, "comments": 150}) == 100
    assert social_reach("x", 50, platform_diversity=3) > 50
    assert social_reach("gdelt", 50, platform_diversity=3) is None


@pytest.mark.asyncio
async def test_source_metadata_api_is_capability_aware_and_secret_safe(db) -> None:
    connectors = {
        "x": XConnector(bearer_token="server-secret"),
        "facebook": facebook_connector(),
        "instagram": InstagramConnector(),
    }
    seed_database(db, connectors)
    statuses = {status.key: status for status in await list_sources(db, connectors)}
    assert statuses["x"].category == "social"
    assert statuses["x"].capabilities["historical_search"] == "conditional"
    assert statuses["facebook"].configuration_state == "restricted"
    assert statuses["instagram"].capabilities["keyword_search"] is False
    assert "server-secret" not in str([status.model_dump() for status in statuses.values()])


class SocialFixtureConnector(BaseConnector):
    def __init__(self, key: str, item: ConnectorItem):
        self.metadata = ConnectorMetadata(
            key=key,
            name=key,
            kind="social",
            base_url=f"mock://{key}",
            category="social",
            capabilities=ConnectorCapabilities(
                keyword_search=True,
                public_posts=True,
                engagement_metrics=True,
                content_types=("posts",),
            ),
        )
        super().__init__()
        self.item = item

    def validate_configuration(self):
        return True, None

    async def search(self, query: str, *, limit: int, since=None):
        self.last_diagnostics.raw_result_count = 1
        self.last_diagnostics.normalized_result_count = 1
        return [self.item]

    def normalize(self, payload):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_social_search_persists_nullable_metrics_and_platform_analytics(
    db, settings: Settings
) -> None:
    def fixture(source: str) -> ConnectorItem:
        return ConnectorItem(
            source=source,
            external_id=f"{source}-1",
            canonical_url="https://public.example/shared",
            author="Observer",
            author_handle="observer",
            author_verified=None,
            title="Baghdad public update",
            text="Baghdad public update #Iraq @desk",
            published_at=datetime.now(UTC),
            language="en",
            hashtags=("Iraq",),
            mentions=("desk",),
            media_type="post",
            raw_metrics={"likes": 10},
            raw_metadata={"source_type": "post"},
        )

    connectors = {
        "social_one": SocialFixtureConnector("social_one", fixture("social_one")),
        "social_two": SocialFixtureConnector("social_two", fixture("social_two")),
    }
    seed_database(db, connectors)
    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="Baghdad", sources=list(connectors))
    )
    response = get_search_response(db, session_id)
    assert response.session.result_count == 2
    assert response.results[0].like_count == 10
    assert response.results[0].view_count is None
    assert response.results[0].hashtags == ["Iraq"]
    assert response.results[0].duplicate_count == 1
    assert response.analytics["platform_diversity"] == 2
    assert response.analytics["category_distribution"] == {"social": 2}
    assert response.clusters[0].platform_diversity == 2
    assert response.clusters[0].first_seen_by_mirsad is not None
