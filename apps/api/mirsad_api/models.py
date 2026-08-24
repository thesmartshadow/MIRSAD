from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def public_id() -> str:
    return str(uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """Store SQLite timestamps as UTC and always restore timezone-aware values."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        return dialect.type_descriptor(DateTime(timezone=dialect.name != "sqlite"))

    def process_bind_param(self, value: datetime | None, dialect: Dialect):
        if value is None:
            return None
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.replace(tzinfo=None) if dialect.name == "sqlite" else aware

    def process_result_value(self, value: datetime | None, _dialect: Dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    configured: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float] = mapped_column(Float, default=70.0)
    config_public: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    recent_failure: Mapped[str | None] = mapped_column(Text)
    failure_category: Mapped[str | None] = mapped_column(String(40))
    http_status: Mapped[int | None] = mapped_column(Integer)
    average_latency_ms: Mapped[float] = mapped_column(Float, default=0)
    last_latency_ms: Mapped[float] = mapped_column(Float, default=0)
    last_result_count: Mapped[int] = mapped_column(Integer, default=0)
    last_normalized_count: Mapped[int] = mapped_column(Integer, default=0)
    last_malformed_count: Mapped[int] = mapped_column(Integer, default=0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_query: Mapped[str] = mapped_column(String(300))
    normalized_query: Mapped[str] = mapped_column(String(300), index=True)
    detected_language: Mapped[str] = mapped_column(String(10), default="und")
    tokens: Mapped[list[str]] = mapped_column(JSON, default=list)
    variants: Mapped[list[str]] = mapped_column(JSON, default=list)
    exact_phrase: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SearchSession(Base):
    __tablename__ = "search_sessions"
    __table_args__ = (Index("ix_search_sessions_started_at", "started_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=public_id)
    query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_content_source_external"),
        Index("ix_content_published_source", "published_at", "source_id"),
        Index("ix_content_fingerprint", "content_fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), default=public_id, unique=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(300))
    canonical_url: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    author_handle: Mapped[str | None] = mapped_column(String(300))
    author_verified: Mapped[bool | None] = mapped_column(Boolean)
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    language: Mapped[str] = mapped_column(String(10), default="und", index=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON)
    mentions: Mapped[list[str] | None] = mapped_column(JSON)
    media_type: Mapped[str | None] = mapped_column(String(40), index=True)
    acquisition_mode: Mapped[str] = mapped_column(String(30), default="DIRECT_API", index=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    normalized_title: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    normalized_author: Mapped[str] = mapped_column(Text, default="")


class ContentMetric(Base):
    __tablename__ = "content_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), unique=True, index=True
    )
    raw_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    like_count: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int | None] = mapped_column(Integer)
    comment_count: Mapped[int | None] = mapped_column(Integer)
    share_count: Mapped[int | None] = mapped_column(Integer)
    repost_count: Mapped[int | None] = mapped_column(Integer)
    reaction_count: Mapped[int | None] = mapped_column(Integer)
    normalized_engagement: Mapped[float] = mapped_column(Float, default=0)
    adapter_version: Mapped[str] = mapped_column(String(30), default="v1")


class ContentScore(Base):
    __tablename__ = "content_scores"
    __table_args__ = (
        UniqueConstraint("search_session_id", "content_item_id", name="uq_session_item_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), index=True)
    final_score: Mapped[float] = mapped_column(Float, index=True)
    relevance: Mapped[float] = mapped_column(Float)
    freshness: Mapped[float] = mapped_column(Float)
    engagement: Mapped[float] = mapped_column(Float)
    source_confidence: Mapped[float] = mapped_column(Float)
    cross_source_presence: Mapped[float] = mapped_column(Float)
    novelty: Mapped[float] = mapped_column(Float)
    spam_penalty: Mapped[float] = mapped_column(Float)
    matched_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        UniqueConstraint("search_session_id", "content_item_id", name="uq_session_item_result"),
        Index("ix_search_result_session_rank", "search_session_id", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    duplicate_group_id: Mapped[str | None] = mapped_column(String(36), index=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), index=True)
    acquisition_path: Mapped[str | None] = mapped_column(String(30))
    acquisition_paths: Mapped[list[str] | None] = mapped_column(JSON)


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=public_id)
    search_session_id: Mapped[str] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    canonical_item_id: Mapped[int | None] = mapped_column(ForeignKey("content_items.id"))
    source_count: Mapped[int] = mapped_column(Integer, default=1)
    source_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    record_count: Mapped[int] = mapped_column(Integer, default=1)
    earliest_seen: Mapped[datetime | None] = mapped_column(UTCDateTime())
    latest_seen: Mapped[datetime | None] = mapped_column(UTCDateTime())


class DuplicateGroupMember(Base):
    __tablename__ = "duplicate_group_members"
    __table_args__ = (
        UniqueConstraint("duplicate_group_id", "content_item_id", name="uq_duplicate_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    duplicate_group_id: Mapped[str] = mapped_column(ForeignKey("duplicate_groups.id"), index=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), index=True)
    similarity: Mapped[float] = mapped_column(Float, default=1)
    match_stage: Mapped[str] = mapped_column(String(30))


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=public_id)
    search_session_id: Mapped[str] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    representative_title: Mapped[str] = mapped_column(Text)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    source_distribution: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    platform_diversity: Mapped[int] = mapped_column(Integer, default=1)
    earliest_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    latest_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    aggregate_score: Mapped[float] = mapped_column(Float, default=0)
    terms: Mapped[list[str]] = mapped_column(JSON, default=list)


class ClusterMember(Base):
    __tablename__ = "cluster_members"
    __table_args__ = (UniqueConstraint("cluster_id", "content_item_id", name="uq_cluster_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey("clusters.id"), index=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"), index=True)
    similarity: Mapped[float] = mapped_column(Float)


class AnalyticsRecord(Base):
    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    metric_key: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[Any] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    category: Mapped[str] = mapped_column(String(40), index=True)
    safe_for_client: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class ConnectorRunRecord(Base):
    __tablename__ = "connector_runs"
    __table_args__ = (Index("ix_connector_run_session_source", "search_session_id", "source_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="CASCADE"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30))
    error_category: Mapped[str | None] = mapped_column(String(40))
    http_status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    raw_result_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_result_count: Mapped[int] = mapped_column(Integer, default=0)
    schema_valid_count: Mapped[int] = mapped_column(Integer, default=0)
    query_match_count: Mapped[int] = mapped_column(Integer, default=0)
    time_eligible_count: Mapped[int] = mapped_column(Integer, default=0)
    normalized_result_count: Mapped[int] = mapped_column(Integer, default=0)
    malformed_count: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    attempt_latencies_ms: Mapped[list[float]] = mapped_column(JSON, default=list)
    circuit_breaker_state: Mapped[str] = mapped_column(String(20), default="closed")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=public_id)
    name: Mapped[str] = mapped_column(String(120), index=True)
    query: Mapped[str] = mapped_column(String(300))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("content_item_id", name="uq_bookmark_content_item"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=public_id)
    content_item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    search_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class ResponseCache(Base):
    __tablename__ = "response_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[Any] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class DiscoveryRecord(Base):
    __tablename__ = "discovery_records"
    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_discovery_canonical_url"),
        Index("ix_discovery_platform_last_seen", "platform", "last_seen_at"),
        Index("ix_discovery_content_id", "platform", "canonical_content_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), default=public_id, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(30), index=True)
    canonical_content_id: Mapped[str | None] = mapped_column(String(300))
    indexed_title: Mapped[str | None] = mapped_column(Text)
    indexed_snippet: Mapped[str | None] = mapped_column(Text)
    acquisition_mode: Mapped[str] = mapped_column(String(30), index=True)
    language_hint: Mapped[str | None] = mapped_column(String(20))
    published_at_hint: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_completeness: Mapped[float] = mapped_column(Float, default=0)
    content_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    availability_state: Mapped[str] = mapped_column(String(30), default="indexed")
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class DiscoveryObservation(Base):
    __tablename__ = "discovery_observations"
    __table_args__ = (
        UniqueConstraint(
            "discovery_record_id",
            "engine",
            "discovery_query",
            "query_variant_id",
            name="uq_discovery_observation",
        ),
        Index("ix_discovery_observation_record_seen", "discovery_record_id", "discovered_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    discovery_record_id: Mapped[int] = mapped_column(
        ForeignKey("discovery_records.id", ondelete="CASCADE"), index=True
    )
    engine: Mapped[str] = mapped_column(String(100), index=True)
    discovery_query: Mapped[str] = mapped_column(String(600))
    query_variant_id: Mapped[str] = mapped_column(String(64), index=True)
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class DiscoveryCache(Base):
    __tablename__ = "discovery_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class EntityAliasEdge(Base):
    __tablename__ = "entity_alias_edges"
    __table_args__ = (
        UniqueConstraint(
            "left_normalized",
            "right_normalized",
            "relationship_type",
            name="uq_entity_alias_edge",
        ),
        Index("ix_entity_alias_left_confidence", "left_normalized", "confidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    left_value: Mapped[str] = mapped_column(String(300))
    left_normalized: Mapped[str] = mapped_column(String(300), index=True)
    right_value: Mapped[str] = mapped_column(String(500))
    right_normalized: Mapped[str] = mapped_column(String(500), index=True)
    relationship_type: Mapped[str] = mapped_column(String(40), index=True)
    evidence_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="observed", index=True)
    support_count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class DiscoveryEngineStat(Base):
    __tablename__ = "discovery_engine_stats"
    __table_args__ = (UniqueConstraint("engine", "platform", name="uq_discovery_engine_platform"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    engine: Mapped[str] = mapped_column(String(100), index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    returned_count: Mapped[int] = mapped_column(Integer, default=0)
    target_domain_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_canonical_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    timeout_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_count: Mapped[int] = mapped_column(Integer, default=0)
    captcha_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_total_ms: Mapped[float] = mapped_column(Float, default=0.0)
    current_state: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    cooldown_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(String(300))
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SearchOutcomeEvent(Base):
    __tablename__ = "search_outcome_events"
    __table_args__ = (
        Index("ix_outcome_session_event", "search_session_id", "event_type"),
        Index("ix_outcome_query_class_created", "query_class", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="SET NULL"), index=True
    )
    content_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_items.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    query_class: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    rank: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(50), index=True)
    acquisition_mode: Mapped[str | None] = mapped_column(String(30))
    explicit_judgment: Mapped[str | None] = mapped_column(String(20), index=True)
    algorithm_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class SourceUtilityObservation(Base):
    __tablename__ = "source_utility_observations"
    __table_args__ = (Index("ix_source_utility_class_source", "query_class", "source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="SET NULL"), index=True
    )
    query_class: Mapped[str] = mapped_column(String(40), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    returned_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_count: Mapped[int] = mapped_column(Integer, default=0)
    admitted_count: Mapped[int] = mapped_column(Integer, default=0)
    top_k_count: Mapped[int] = mapped_column(Integer, default=0)
    explicit_relevant_count: Mapped[int] = mapped_column(Integer, default=0)
    explicit_irrelevant_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    failure_category: Mapped[str | None] = mapped_column(String(40))
    duplicate_rate: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class EngineUtilityObservation(Base):
    __tablename__ = "engine_utility_observations"
    __table_args__ = (
        Index("ix_engine_utility_class_target", "query_class", "engine", "target_platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="SET NULL"), index=True
    )
    query_class: Mapped[str] = mapped_column(String(40), index=True)
    engine: Mapped[str] = mapped_column(String(100), index=True)
    target_platform: Mapped[str] = mapped_column(String(50), index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    target_domain_precision: Mapped[float] = mapped_column(Float, default=0)
    canonical_yield: Mapped[int] = mapped_column(Integer, default=0)
    unique_yield: Mapped[int] = mapped_column(Integer, default=0)
    judged_relevant_yield: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    rate_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    captcha_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class ShadowEvaluation(Base):
    __tablename__ = "shadow_evaluations"
    __table_args__ = (Index("ix_shadow_strategy_created", "strategy_type", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="SET NULL"), index=True
    )
    strategy_type: Mapped[str] = mapped_column(String(40), index=True)
    strategy_version: Mapped[str] = mapped_column(String(80))
    production_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    shadow_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    comparison: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class AlgorithmConfigurationSnapshot(Base):
    __tablename__ = "algorithm_configuration_snapshots"
    __table_args__ = (Index("ix_algorithm_snapshot_slot_created", "slot", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=public_id)
    slot: Mapped[str] = mapped_column(String(40), index=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    benchmark_hashes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class EvidenceGraphNode(Base):
    __tablename__ = "evidence_graph_nodes"
    __table_args__ = (
        UniqueConstraint("node_type", "stable_key", name="uq_evidence_graph_node"),
        Index("ix_evidence_graph_type_label", "node_type", "label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_type: Mapped[str] = mapped_column(String(30), index=True)
    stable_key: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(500))
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class EvidenceGraphEdge(Base):
    __tablename__ = "evidence_graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "from_node_id", "to_node_id", "relationship_type", name="uq_evidence_graph_edge"
        ),
        Index("ix_evidence_graph_edge_type", "relationship_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_node_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_graph_nodes.id", ondelete="CASCADE"), index=True
    )
    to_node_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_graph_nodes.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(40), index=True)
    support_count: Mapped[int] = mapped_column(Integer, default=1)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
