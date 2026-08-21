from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .mafer.budget import SearchMode


class TimeRange(StrEnum):
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    ALL = "all"


class SortMode(StrEnum):
    BEST_MATCH = "best_match"
    NEWEST = "newest"
    MOST_ENGAGED = "most_engaged"
    CROSS_PLATFORM = "cross_platform"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    sources: list[str] = Field(
        default_factory=lambda: ["bluesky", "hacker_news", "github", "gdelt", "rss"],
        min_length=1,
        max_length=30,
    )
    time_range: TimeRange = TimeRange.WEEK
    language: Literal["all", "ar", "en"] = "all"
    limit: int = Field(default=50, ge=1, le=200)
    exact_phrase: bool = False
    sort: SortMode = SortMode.BEST_MATCH
    content_types: list[Literal["posts", "videos", "channels", "threads", "issues", "news"]] = (
        Field(default_factory=list, max_length=6)
    )
    has_media: bool | None = None
    has_links: bool | None = None
    hashtags: list[str] = Field(default_factory=list, max_length=10)
    source_options: dict[str, dict[str, Any]] = Field(default_factory=dict)
    search_mode: SearchMode = SearchMode.BALANCED
    source_selection: Literal["auto", "explicit"] = "explicit"

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search query cannot be blank")
        if not any(character.isalnum() for character in value):
            raise ValueError("Search query must contain at least one letter or number")
        return value


    @field_validator("sources")
    @classmethod
    def unique_sources(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("hashtags")
    @classmethod
    def clean_hashtags(cls, value: list[str]) -> list[str]:
        cleaned = [tag.strip().removeprefix("#")[:80] for tag in value if tag.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("source_options")
    @classmethod
    def bounded_source_options(cls, value: dict[str, dict[str, Any]]):
        if len(value) > 30:
            raise ValueError("Too many source option groups")
        if len(str(value)) > 5000:
            raise ValueError("Source options are too large")
        return value


SearchEventName = Literal[
    "search.started",
    "planning.started",
    "planning.completed",
    "source.selected",
    "source.started",
    "source.progress",
    "source.completed",
    "source.degraded",
    "source.failed",
    "source.skipped",
    "collection.progress",
    "normalization.completed",
    "persistence.completed",
    "ranking.started",
    "ranking.completed",
    "clustering.started",
    "clustering.completed",
    "search.partial",
    "search.completed",
    "search.failed",
]


class SearchJobStarted(BaseModel):
    job_id: str
    session_id: str
    status: Literal["started"] = "started"


class SearchJobEvent(BaseModel):
    sequence: int = Field(ge=1)
    event: SearchEventName
    job_id: str
    session_id: str
    elapsed_ms: float = Field(ge=0)
    emitted_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class ConnectorWarning(BaseModel):
    source: str
    code: str
    message: str
    retryable: bool = False
    status_code: int | None = None


class ScoreExplanation(BaseModel):
    final_score: float
    relevance: float
    freshness: float
    engagement: float
    source_confidence: float
    cross_source_presence: float
    novelty: float
    spam_penalty: float
    supporting_signal_factor: float = 1.0
    pre_penalty_score: float | None = None
    weighted_components: dict[str, float] = Field(default_factory=dict)
    lexical_relevance: float
    semantic_relevance: float | None = None
    semantic_similarity: float | None = None
    semantic_weight: float = 0.0
    secondary_quality_budget: float = 0.0
    ranking_strategy: str = "lexical_explainable"
    relevance_features: dict[str, float] = Field(default_factory=dict)
    matched_terms: list[str]
    source: str
    fetched_at: datetime
    published_at: datetime | None
    duplicate_group_id: str | None = None


class HighlightRange(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class SearchResultItem(BaseModel):
    id: str
    source: str
    source_type: str
    acquisition_mode: str
    acquisition_modes_seen: list[str] = Field(default_factory=list)
    indexed_public_web_coverage: bool = False
    discovery_support: int | None = None
    discovery_engines: list[str] = Field(default_factory=list)
    evidence_completeness: str = "UNKNOWN"
    evidence_completeness_score: float | None = None
    external_id: str
    canonical_url: str
    author: str | None
    author_handle: str | None = None
    author_verified: bool | None = None
    title: str | None
    text: str
    relevant_snippet: str
    highlight_ranges: list[HighlightRange] = Field(default_factory=list)
    semantic_only_match: bool = False
    published_at: datetime | None
    fetched_at: datetime
    language: str
    hashtags: list[str] | None = None
    mentions: list[str] | None = None
    media_type: str | None = None
    like_count: int | None = None
    view_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    repost_count: int | None = None
    reaction_count: int | None = None
    raw_metrics: dict[str, Any]
    normalized_engagement: float
    social_reach: float | None = None
    score: float
    matched_terms: list[str]
    duplicate_group_id: str | None
    duplicate_count: int = 0
    related_sources: list[str] = Field(default_factory=list)
    cluster_id: str | None
    explanation: ScoreExplanation


class ClusterSummary(BaseModel):
    id: str
    representative_title: str
    member_count: int
    source_distribution: dict[str, int]
    platform_presence: dict[str, int]
    platform_diversity: int
    first_seen_by_mirsad: datetime | None
    earliest_at: datetime | None
    latest_at: datetime | None
    aggregate_score: float
    terms: list[str]
    member_ids: list[str] = Field(default_factory=list)


class SearchSummary(BaseModel):
    id: str
    original_query: str
    normalized_query: str
    detected_language: str
    status: str
    sources: list[str]
    result_count: int
    unique_count: int
    duration_ms: int
    started_at: datetime
    completed_at: datetime | None
    warnings: list[ConnectorWarning]
    parameters: SearchRequest
    outcome_reason: str | None = None
    outcome_context: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    session: SearchSummary
    results: list[SearchResultItem]
    clusters: list[ClusterSummary]
    analytics: dict[str, Any]


class SearchDiagnostics(BaseModel):
    session_id: str
    diagnostics: dict[str, Any]


class SourceStatus(BaseModel):
    key: str
    name: str
    kind: str
    category: str
    support_level: str
    coverage_label: str | None = None
    capabilities: dict[str, Any]
    configuration_state: str
    active_acquisition_mode: str
    enabled: bool
    configured: bool
    status: str
    detail: str | None = None
    confidence: float
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    recent_failure: str | None = None
    failure_category: str | None = None
    http_status: int | None = None
    average_latency_ms: float = 0
    last_latency_ms: float = 0
    last_result_count: int = 0
    last_normalized_count: int = 0
    last_malformed_count: int = 0
    request_count: int = 0
    failure_count: int = 0
    configuration: dict[str, Any] = Field(default_factory=dict)


class SettingValue(BaseModel):
    key: str
    value: Any
    category: str


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class SystemStatus(BaseModel):
    api_status: str
    database_status: str
    fts_status: str
    connector_status: dict[str, int]
    record_count: int
    index_count: int
    database_integrity: str
    foreign_key_violations: int
    capabilities: list[str]
    version: str


class CompareRequest(BaseModel):
    left_session_id: str
    right_session_id: str


class CompareResponse(BaseModel):
    left: SearchSummary
    right: SearchSummary
    left_analytics: dict[str, Any]
    right_analytics: dict[str, Any]
    collection_window_warning: bool


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    configuration: SearchRequest

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


class SavedSearchUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def trim_updated_name(cls, value: str) -> str:
        return value.strip()


class SavedSearchView(BaseModel):
    id: str
    name: str
    configuration: SearchRequest
    created_at: datetime
    updated_at: datetime


class BookmarkCreate(BaseModel):
    content_id: str
    search_session_id: str | None = None
    note: str = Field(default="", max_length=1000)


class BookmarkUpdate(BaseModel):
    note: str = Field(max_length=1000)


class BookmarkView(BaseModel):
    id: str
    content_id: str
    source: str
    source_type: str
    author: str | None
    title: str | None
    published_at: datetime | None
    canonical_url: str
    search_session_id: str | None
    discovered_query: str | None
    note: str
    created_at: datetime
    updated_at: datetime


class DuplicateMemberView(BaseModel):
    id: str
    source: str
    source_type: str
    author: str | None
    title: str | None
    text: str
    canonical_url: str
    published_at: datetime | None
    engagement: float
    similarity: float
    match_stage: str
    representative: bool


class DuplicateGroupView(BaseModel):
    id: str
    source_count: int
    source_names: list[str]
    record_count: int
    earliest_seen: datetime | None
    latest_seen: datetime | None
    representative_id: str | None
    members: list[DuplicateMemberView]


class DataCounts(BaseModel):
    search_sessions: int
    content_items: int
    bookmarks: int
    saved_searches: int
    cached_responses: int
    indexed_records: int


class ConfirmAction(BaseModel):
    confirm: bool


class DataActionResult(BaseModel):
    action: str
    affected: int
    counts: DataCounts


class ManualImportCreate(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    title: str | None = Field(default=None, max_length=1_000)
    selected_text: str = Field(min_length=1, max_length=20_000)

    @field_validator("url", "selected_text")
    @classmethod
    def trim_manual_import(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class ManualImportView(BaseModel):
    id: str
    source: str
    canonical_url: str
    acquisition_mode: Literal["MANUAL_IMPORT"]
    duplicate: bool


class OutcomeEventCreate(BaseModel):
    event_type: Literal[
        "RESULT_OPENED",
        "RESULT_MARKED_RELEVANT",
        "RESULT_MARKED_NOT_RELEVANT",
        "SEARCH_REFORMULATED",
    ]
    search_session_id: str = Field(min_length=36, max_length=36)
    content_id: str | None = Field(default=None, min_length=36, max_length=36)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def bounded_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 10 or len(str(value)) > 2_000:
            raise ValueError("Outcome context is too large")
        return value


class OutcomeEventView(BaseModel):
    id: int
    event_type: str
    search_session_id: str | None
    content_id: str | None
    query_class: str
    rank: int | None
    source: str | None
    acquisition_mode: str | None
    explicit_judgment: str | None
    created_at: datetime


class QualitySummary(BaseModel):
    search_count: int
    zero_result_count: int
    zero_result_rate: float
    explicit_relevant: int
    explicit_not_relevant: int
    query_class_distribution: dict[str, int]
    language_distribution: dict[str, int]
    source_utility: list[dict[str, Any]]
    engine_utility: list[dict[str, Any]]
    average_rounds: float
    stop_reasons: dict[str, int]
    uncertainty_distribution: dict[str, int]
    average_latency_ms: float
    average_request_count: float
    shadow_comparisons: dict[str, int]
    configuration_snapshots: list[dict[str, Any]]


class RollbackRequest(BaseModel):
    confirm: bool
    reason: str = Field(min_length=3, max_length=300)
