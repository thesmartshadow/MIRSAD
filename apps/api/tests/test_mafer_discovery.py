from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from mirsad_api.connectors import RedditConnector, ThreadsConnector, XConnector
from mirsad_api.discovery.classifiers import (
    ContentType,
    classify_reddit_url,
    classify_threads_url,
    classify_x_url,
)
from mirsad_api.discovery.common_crawl import CommonCrawlAdapter
from mirsad_api.discovery.enrichment import OfficialEmbedEnricher
from mirsad_api.discovery.repository import DiscoveryRepository
from mirsad_api.discovery.searxng import DiscoveryProviderError, SearxngClient
from mirsad_api.discovery.service import WebSocialDiscoveryService
from mirsad_api.models import DiscoveryCache, DiscoveryObservation, DiscoveryRecord
from mirsad_api.provenance import AcquisitionMode


def test_x_url_classifier_accepts_posts_and_rejects_profiles_as_content() -> None:
    normal = classify_x_url(
        "https://twitter.com/MIRSAD/status/1234567890?utm_source=index#fragment"
    )
    anonymous = classify_x_url("https://x.com/i/web/status/99887766")
    profile = classify_x_url("https://x.com/MIRSAD")

    assert normal is not None
    assert normal.content_type == ContentType.POST
    assert normal.canonical_url == "https://x.com/MIRSAD/status/1234567890"
    assert anonymous is not None
    assert anonymous.canonical_url == "https://x.com/i/web/status/99887766"
    assert profile is not None and profile.content_type == ContentType.PROFILE
    assert not profile.is_content


def test_threads_url_classifier_separates_posts_and_profiles() -> None:
    post = classify_threads_url("https://threads.net/@mirsad/post/ABC_123?x=1")
    short = classify_threads_url("https://www.threads.com/t/DEF-456")
    profile = classify_threads_url("https://threads.com/@mirsad")

    assert post is not None and post.content_type == ContentType.POST
    assert post.canonical_url == "https://www.threads.com/@mirsad/post/ABC_123"
    assert short is not None and short.canonical_content_id == "DEF-456"
    assert profile is not None and profile.content_type == ContentType.PROFILE


def test_reddit_url_classifier_distinguishes_content_and_navigation() -> None:
    post = classify_reddit_url(
        "https://old.reddit.com/r/technology/comments/abc123/story_title/?utm_source=x"
    )
    comment = classify_reddit_url(
        "https://reddit.com/r/technology/comments/abc123/story_title/def456/"
    )
    short = classify_reddit_url("https://redd.it/abc123")
    community = classify_reddit_url("https://reddit.com/r/technology")
    profile = classify_reddit_url("https://reddit.com/user/researcher")

    assert post is not None and post.content_type == ContentType.POST
    assert comment is not None and comment.content_type == ContentType.COMMENT
    assert comment.canonical_content_id == "abc123:def456"
    assert short is not None and short.content_type == ContentType.POST
    assert community is not None and community.content_type == ContentType.COMMUNITY
    assert profile is not None and profile.content_type == ContentType.PROFILE


@pytest.mark.parametrize(
    ("classifier", "url"),
    [
        (classify_x_url, "javascript:alert(1)"),
        (classify_x_url, "https://x.com@example.org/user/status/12345"),
        (classify_x_url, "https://127.0.0.1/user/status/12345"),
        (classify_threads_url, "data:text/html,hello"),
        (classify_threads_url, "https://thrеads.net/@name/post/ABC123"),
        (classify_reddit_url, "file:///etc/passwd"),
        (classify_reddit_url, "https://evil.example/r/x/comments/abc123/title"),
        (classify_reddit_url, "not a URL"),
    ],
)
def test_platform_classifiers_reject_unsafe_or_wrong_domains(classifier, url: str) -> None:
    assert classifier(url) is None


def _repository(test_engine: Engine) -> DiscoveryRepository:
    return DiscoveryRepository(
        sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    )


@pytest.mark.asyncio
async def test_web_discovery_validates_domains_deduplicates_and_persists_support(
    test_engine: Engine,
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://twitter.com/city/status/123456?utm_source=one",
                        "title": "بغداد technology update",
                        "content": "Public technology announcement in Baghdad",
                        "engines": ["brave", "qwant"],
                        "language": "ar",
                    },
                    {
                        "url": "https://x.com/city/status/123456?ref=two",
                        "title": "Same indexed post",
                        "content": "A duplicate discovery path",
                        "engine": "duckduckgo",
                    },
                    {
                        "url": "https://example.org/city/status/123456",
                        "title": "Wrong domain despite site operator",
                        "content": "Rejected",
                        "engine": "brave",
                    },
                    {
                        "url": "https://x.com/city",
                        "title": "City profile",
                        "content": "Profile is remembered but not emitted as a post",
                        "engine": "qwant",
                    },
                ],
                "unresponsive_engines": [
                    ["startpage", "timeout"],
                    ["qwant", "Suspended: too many requests"],
                ],
            },
        )

    repository = _repository(test_engine)
    service = WebSocialDiscoveryService(
        enabled=True,
        client=SearxngClient(
            "http://127.0.0.1:8080",
            engines=("brave", "duckduckgo", "qwant"),
            transport=httpx.MockTransport(handler),
        ),
        repository=repository,
        variant_limit=1,
    )
    result = await service.search(
        "x",
        "بغداد technology",
        limit=10,
        query_variants=("بغداد technology",),
    )
    cached = await service.search(
        "x",
        "بغداد technology",
        limit=10,
        query_variants=("بغداد technology",),
    )

    assert calls == 1
    assert result.returned_count == 4
    assert result.target_domain_count == 3
    assert result.canonical_content_count == 1
    assert result.profile_count == 1
    assert result.duplicate_count == 1
    assert result.candidates[0].engines_that_found_it == (
        "brave",
        "duckduckgo",
        "qwant",
    )
    assert result.candidates[0].number_of_independent_discoveries == 3
    assert cached.cache_state == "cached"
    assert any(row.timeout and row.engine == "startpage" for row in result.telemetry)
    assert any(row.rate_limited and row.engine == "qwant" for row in result.telemetry)
    assert {
        row.engine: row.accepted_canonical_result_count
        for row in result.telemetry
        if row.engine in {"brave", "duckduckgo", "qwant"}
    } == {"brave": 1, "duckduckgo": 1, "qwant": 2}

    factory = sessionmaker(bind=test_engine)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DiscoveryRecord)) == 2
        assert db.scalar(select(func.count()).select_from(DiscoveryObservation)) >= 4

    items = service.to_connector_items(result)
    assert len(items) == 1
    assert items[0].acquisition_mode == AcquisitionMode.WEB_INDEX
    assert items[0].raw_metrics == {}
    assert items[0].raw_metadata["direct_platform_api"] is False


@pytest.mark.asyncio
async def test_social_connectors_use_shared_web_discovery_when_api_credentials_absent() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        if "site:x.com" in query:
            url = "https://x.com/public/status/123456"
        elif "site:threads.com" in query:
            url = "https://threads.net/@public/post/THREAD123"
        else:
            url = "https://reddit.com/r/technology/comments/abc123/public_story"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": url,
                        "title": "Technology public record",
                        "content": "A public technology record discovered by a local index.",
                        "engine": "brave",
                    }
                ]
            },
        )

    service = WebSocialDiscoveryService(
        enabled=True,
        client=SearxngClient(
            "http://localhost:8080", transport=httpx.MockTransport(handler)
        ),
        variant_limit=1,
    )
    connectors = (
        XConnector(web_discovery=service),
        ThreadsConnector(web_discovery=service),
        RedditConnector(web_discovery=service),
    )

    for connector in connectors:
        configured, detail = connector.validate_configuration()
        items = await connector.search("technology", limit=5)
        assert configured is True
        assert detail == (
            "Indexed public web coverage; not direct X API search"
            if connector.metadata.key == "x"
            else "Indexed public web coverage; not Threads API search"
            if connector.metadata.key == "threads"
            else "Indexed public web coverage; not Reddit Data API search"
        )
        assert connector.active_acquisition_mode() == AcquisitionMode.WEB_INDEX.value
        assert len(items) == 1
        assert items[0].source == connector.metadata.key
        assert items[0].acquisition_mode == AcquisitionMode.WEB_INDEX


@pytest.mark.asyncio
async def test_searxng_classifies_rate_limit_and_timeout() -> None:
    async def limited(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "limited"})

    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(DiscoveryProviderError, match="rate limit") as rate_error:
        await SearxngClient(
            "http://localhost:8080", transport=httpx.MockTransport(limited)
        ).search("technology")
    assert rate_error.value.code == "rate_limited"
    with pytest.raises(DiscoveryProviderError, match="timed out") as timeout_error:
        await SearxngClient(
            "http://localhost:8080", transport=httpx.MockTransport(timeout)
        ).search("technology")
    assert timeout_error.value.code == "timeout"


@pytest.mark.asyncio
async def test_searxng_rejects_malformed_payload() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": "not-a-list"})

    with pytest.raises(DiscoveryProviderError) as error:
        await SearxngClient(
            "http://localhost:8080", transport=httpx.MockTransport(handler)
        ).search("technology")
    assert error.value.code == "invalid_payload"


@pytest.mark.asyncio
async def test_searxng_health_rejects_http_200_when_upstream_engines_all_fail() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [],
                "unresponsive_engines": [
                    ["brave", "Suspended: too many requests"],
                    ["duckduckgo", "CAPTCHA"],
                ],
            },
        )

    healthy, code, _latency = await SearxngClient(
        "http://localhost:8080", transport=httpx.MockTransport(handler)
    ).health_check()

    assert healthy is False
    assert code == "upstream_engines_unavailable"


@pytest.mark.asyncio
async def test_web_connector_reports_upstream_degradation_for_empty_http_200(
    test_engine: Engine,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [],
                "unresponsive_engines": [
                    ["brave", "Suspended: too many requests"],
                    ["duckduckgo", "CAPTCHA required"],
                ],
            },
        )

    service = WebSocialDiscoveryService(
        enabled=True,
        client=SearxngClient(
            "http://127.0.0.1:8080",
            engines=("brave", "duckduckgo"),
            transport=httpx.MockTransport(handler),
        ),
        repository=_repository(test_engine),
        variant_limit=1,
    )
    connector = XConnector(web_discovery=service)

    items = await connector.search("open source", limit=10)

    assert items == []
    assert connector.last_diagnostics.http_status == 200
    assert connector.last_diagnostics.warning_code == "partial_engine_failure"
    assert connector.last_diagnostics.normalized_result_count == 0
    engine_rows = connector.last_diagnostics.details["engine_telemetry"]
    assert {row["engine"] for row in engine_rows} == {"brave", "duckduckgo"}
    assert any(row["rate_limited"] for row in engine_rows)
    assert any(row["error"] == "CAPTCHA required" for row in engine_rows)


@pytest.mark.asyncio
async def test_expired_discovery_cache_is_reported_as_stale_fallback(
    test_engine: Engine,
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://x.com/public/status/123456",
                        "title": "Technology update",
                        "content": "Public technology post",
                        "engine": "brave",
                    }
                ]
            },
        )

    repository = _repository(test_engine)
    service = WebSocialDiscoveryService(
        enabled=True,
        client=SearxngClient(
            "http://localhost:8080", transport=httpx.MockTransport(handler)
        ),
        repository=repository,
        variant_limit=1,
    )
    await service.search("x", "technology", limit=5, query_variants=("technology",))
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    with factory() as db:
        cache = db.scalar(select(DiscoveryCache))
        assert cache is not None
        cache.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    result = await service.search(
        "x", "technology", limit=5, query_variants=("technology",)
    )

    assert calls == 2
    assert result.cache_state == "stale_fallback"
    assert len(result.candidates) == 1


@pytest.mark.asyncio
async def test_official_embed_enrichment_discards_provider_html() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "author_name": "Public author",
                "provider_name": "X",
                "html": "<script>steal()</script><blockquote>source text</blockquote>",
            },
        )

    result = await OfficialEmbedEnricher(
        enabled=True, transport=httpx.MockTransport(handler)
    ).enrich("x", "https://x.com/public/status/123456")

    assert result.state == "enriched"
    assert result.metadata == {"author_name": "Public author", "provider_name": "X"}
    assert "html" not in result.metadata


@pytest.mark.asyncio
async def test_common_crawl_only_returns_metadata_for_exact_validated_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("collinfo.json"):
            return httpx.Response(200, json=[{"id": "CC-MAIN-2026-30"}])
        payload = "\n".join(
            [
                json.dumps(
                    {
                        "url": "https://x.com/public/status/123456?tracking=1",
                        "timestamp": "20260810110000",
                        "status": "200",
                        "mime": "text/html",
                        "digest": "ABC",
                    }
                ),
                json.dumps(
                    {
                        "url": "https://example.org/not-the-target",
                        "timestamp": "20260810110100",
                        "status": "200",
                    }
                ),
            ]
        )
        return httpx.Response(200, text=payload)

    adapter = CommonCrawlAdapter(transport=httpx.MockTransport(handler))
    lookup = await adapter.lookup("x", "https://x.com/public/status/123456")

    assert lookup.collection == "CC-MAIN-2026-30"
    assert len(lookup.captures) == 1
    assert lookup.captures[0].timestamp == "2026-08-10T11:00:00Z"
    with pytest.raises(DiscoveryProviderError) as error:
        await adapter.lookup("x", "artificial intelligence")
    assert error.value.code == "invalid_historical_target"
