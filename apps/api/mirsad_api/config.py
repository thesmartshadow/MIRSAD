from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="MIRSAD_", env_ignore_empty=True, extra="ignore"
    )

    app_name: str = "MIRSAD"
    version: str = "1.1.1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/mirsad.db"
    web_origin: str = "http://127.0.0.1:5173"
    log_level: str = "INFO"
    enable_mock_connector: bool = False
    github_token: str | None = Field(default=None, validation_alias="GITHUB_TOKEN")
    github_scopes: str = "repositories"
    youtube_api_key: str | None = Field(default=None, validation_alias="YOUTUBE_API_KEY")
    x_bearer_token: str | None = Field(default=None, validation_alias="X_BEARER_TOKEN")
    x_archive_access: bool = False
    threads_access_token: str | None = Field(default=None, validation_alias="THREADS_ACCESS_TOKEN")
    telegram_api_id: int | None = Field(default=None, validation_alias="TELEGRAM_API_ID")
    telegram_api_hash: str | None = Field(default=None, validation_alias="TELEGRAM_API_HASH")
    telegram_session_string: str | None = Field(
        default=None, validation_alias="TELEGRAM_SESSION_STRING"
    )
    reddit_client_id: str | None = Field(default=None, validation_alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str | None = Field(default=None, validation_alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = "MIRSAD/1.1.1 local institutional research"
    mastodon_base_url: str | None = Field(default=None, validation_alias="MASTODON_BASE_URL")
    mastodon_access_token: str | None = Field(
        default=None, validation_alias="MASTODON_ACCESS_TOKEN"
    )
    mastodon_public_instances: str = Field(
        default="https://mas.to", validation_alias="MASTODON_PUBLIC_INSTANCES"
    )
    mastodon_public_pages: int = Field(default=1, ge=1, le=2)
    mastodon_public_records_per_instance: int = Field(default=40, ge=1, le=80)
    mastodon_instance_concurrency: int = Field(default=3, ge=1, le=4)
    instagram_access_token: str | None = Field(
        default=None, validation_alias="INSTAGRAM_ACCESS_TOKEN"
    )
    instagram_user_id: str | None = Field(default=None, validation_alias="INSTAGRAM_USER_ID")
    meta_graph_version: str = "v23.0"
    tiktok_client_key: str | None = Field(default=None, validation_alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str | None = Field(default=None, validation_alias="TIKTOK_CLIENT_SECRET")
    tiktok_research_approved: bool = False
    rss_feeds: str = "https://feeds.bbci.co.uk/news/world/rss.xml"
    request_timeout_seconds: float = 8.0
    connector_retries: int = 1
    gdelt_attempt_timeout_seconds: float = Field(default=1.25, ge=0.25, le=5.0)
    gdelt_total_budget_seconds: float = Field(default=3.0, ge=0.5, le=8.0)
    gdelt_retries: int = Field(default=1, ge=0, le=2)
    gdelt_circuit_failure_threshold: int = Field(default=2, ge=1, le=10)
    gdelt_circuit_cooldown_seconds: float = Field(default=60.0, ge=1.0, le=600.0)
    max_query_length: int = 300
    max_result_limit: int = 200
    freshness_half_life_hours: float = 48.0
    semantic_ranking_enabled: bool = True
    semantic_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    semantic_model_version: str = "fastembed-mean-pooling-v1"
    semantic_model_cache_dir: str = "data/models"
    semantic_local_files_only: bool = True
    semantic_candidate_limit: int = Field(default=20, ge=5, le=100)
    semantic_relevance_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    semantic_quality_budget: float = Field(default=0.01, ge=0.0, le=0.05)
    semantic_threads: int = Field(default=4, ge=1, le=16)
    source_pre_candidate_limit: int = Field(default=50, ge=5, le=200)
    search_job_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    search_job_max_entries: int = Field(default=32, ge=4, le=128)
    search_job_event_limit: int = Field(default=128, ge=32, le=512)
    searxng_enabled: bool = Field(default=False, validation_alias="SEARXNG_ENABLED")
    searxng_url: str = Field(default="http://127.0.0.1:8080", validation_alias="SEARXNG_URL")
    searxng_engines: str = ""
    searxng_timeout_seconds: float = Field(default=4.0, ge=0.5, le=10.0)
    discovery_cache_ttl_seconds: int = Field(default=900, ge=30, le=86400)
    discovery_cache_max_entries: int = Field(default=500, ge=10, le=5000)
    discovery_query_variant_limit: int = Field(default=2, ge=1, le=3)
    discovery_embed_enabled: bool = False
    common_crawl_enabled: bool = False
    common_crawl_url: str = "https://index.commoncrawl.org"
    common_crawl_timeout_seconds: float = Field(default=3.0, ge=0.5, le=8.0)
    common_crawl_max_captures: int = Field(default=10, ge=1, le=25)

    relevance_weight: float = 0.35
    freshness_weight: float = 0.20
    engagement_weight: float = 0.15
    source_confidence_weight: float = 0.10
    cross_source_weight: float = 0.10
    novelty_weight: float = 0.10

    @field_validator("database_url")
    @classmethod
    def ensure_database_parent(cls, value: str) -> str:
        prefix = "sqlite:///"
        if value.startswith(prefix) and value != "sqlite:///:memory:":
            path = Path(value.removeprefix(prefix))
            path.parent.mkdir(parents=True, exist_ok=True)
        return value

    @property
    def ranking_weights(self) -> dict[str, float]:
        weights = {
            "relevance": self.relevance_weight,
            "freshness": self.freshness_weight,
            "engagement": self.engagement_weight,
            "source_confidence": self.source_confidence_weight,
            "cross_source_presence": self.cross_source_weight,
            "novelty": self.novelty_weight,
        }
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError("Enabled ranking weights must total 1.0")
        return weights

    @property
    def parsed_github_scopes(self) -> list[str]:
        valid = {"repositories", "issues", "pull_requests"}
        values = [value.strip() for value in self.github_scopes.split(",")]
        return [value for value in values if value in valid] or ["repositories"]

    @property
    def parsed_mastodon_public_instances(self) -> list[str]:
        return [
            value.strip()
            for value in self.mastodon_public_instances.split(",")[:4]
            if value.strip()
        ]

    @property
    def parsed_searxng_engines(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                value.strip() for value in self.searxng_engines.split(",")[:20] if value.strip()
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
