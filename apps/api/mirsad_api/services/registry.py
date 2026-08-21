from __future__ import annotations

from ..config import Settings
from ..connectors import (
    BaseConnector,
    BlueskyConnector,
    GdeltConnector,
    GitHubConnector,
    HackerNewsConnector,
    InstagramConnector,
    MastodonConnector,
    MockConnector,
    RedditConnector,
    RssConnector,
    TelegramConnector,
    ThreadsConnector,
    TikTokConnector,
    XConnector,
    YouTubeConnector,
    facebook_connector,
    linkedin_connector,
)
from ..database import SessionLocal
from ..discovery.common_crawl import CommonCrawlAdapter
from ..discovery.enrichment import OfficialEmbedEnricher
from ..discovery.repository import DiscoveryRepository
from ..discovery.searxng import SearxngClient
from ..discovery.service import WebSocialDiscoveryService


def build_connector_registry(settings: Settings) -> dict[str, BaseConnector]:
    common = {
        "timeout": settings.request_timeout_seconds,
        "retries": settings.connector_retries,
    }
    repository = DiscoveryRepository(
        SessionLocal, cache_max_entries=settings.discovery_cache_max_entries
    )
    searxng_client = (
        SearxngClient(
            settings.searxng_url,
            timeout=settings.searxng_timeout_seconds,
            engines=settings.parsed_searxng_engines,
        )
        if settings.searxng_enabled
        else None
    )
    common_crawl = (
        CommonCrawlAdapter(
            settings.common_crawl_url,
            timeout=settings.common_crawl_timeout_seconds,
            max_captures=settings.common_crawl_max_captures,
        )
        if settings.common_crawl_enabled
        else None
    )
    web_discovery = WebSocialDiscoveryService(
        enabled=settings.searxng_enabled,
        client=searxng_client,
        repository=repository,
        cache_ttl_seconds=settings.discovery_cache_ttl_seconds,
        variant_limit=settings.discovery_query_variant_limit,
        embed_enricher=OfficialEmbedEnricher(
            enabled=settings.discovery_embed_enabled,
            timeout=min(3.0, settings.request_timeout_seconds),
        ),
        common_crawl=common_crawl,
    )
    connectors: list[BaseConnector] = [
        XConnector(
            bearer_token=settings.x_bearer_token,
            archive_access=settings.x_archive_access,
            web_discovery=web_discovery,
            **common,
        ),
        ThreadsConnector(
            access_token=settings.threads_access_token,
            web_discovery=web_discovery,
            **common,
        ),
        TelegramConnector(
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            session_string=settings.telegram_session_string,
            **common,
        ),
        RedditConnector(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            web_discovery=web_discovery,
            **common,
        ),
        BlueskyConnector(**common),
        HackerNewsConnector(**common),
        GitHubConnector(
            token=settings.github_token,
            scopes=settings.parsed_github_scopes,
            **common,
        ),
        GdeltConnector(
            timeout=min(
                settings.gdelt_attempt_timeout_seconds,
                settings.request_timeout_seconds,
            ),
            retries=settings.gdelt_retries,
            total_budget_seconds=settings.gdelt_total_budget_seconds,
            circuit_failure_threshold=settings.gdelt_circuit_failure_threshold,
            circuit_cooldown_seconds=settings.gdelt_circuit_cooldown_seconds,
        ),
        RssConnector(
            feed_urls=[feed.strip() for feed in settings.rss_feeds.split(",") if feed.strip()],
            **common,
        ),
        YouTubeConnector(api_key=settings.youtube_api_key, **common),
        MastodonConnector(
            instance_url=settings.mastodon_base_url,
            access_token=settings.mastodon_access_token,
            public_instances=settings.parsed_mastodon_public_instances,
            public_pages=settings.mastodon_public_pages,
            public_records_per_instance=settings.mastodon_public_records_per_instance,
            instance_concurrency=settings.mastodon_instance_concurrency,
            **common,
        ),
        InstagramConnector(
            access_token=settings.instagram_access_token,
            user_id=settings.instagram_user_id,
            graph_version=settings.meta_graph_version,
            **common,
        ),
        TikTokConnector(
            client_key=settings.tiktok_client_key,
            client_secret=settings.tiktok_client_secret,
            research_approved=settings.tiktok_research_approved,
            **common,
        ),
        facebook_connector(**common),
        linkedin_connector(**common),
    ]
    if settings.enable_mock_connector:
        connectors.append(MockConnector(**common))
    return {connector.metadata.key: connector for connector in connectors}
