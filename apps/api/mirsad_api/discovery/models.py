from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..provenance import AcquisitionMode
from .classifiers import ClassifiedUrl, ContentType


@dataclass(frozen=True, slots=True)
class EngineTelemetry:
    engine: str
    query_variant_id: str
    target_platform: str
    latency_ms: float | None = None
    returned_result_count: int = 0
    target_domain_result_count: int = 0
    accepted_canonical_result_count: int = 0
    duplicate_count: int = 0
    timeout: bool = False
    rate_limited: bool = False
    error: str | None = None
    current_state: str = "UNKNOWN"
    cooldown_remaining_seconds: float = 0.0
    historical_performance: dict[str, float | str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "query_variant_id": self.query_variant_id,
            "target_platform": self.target_platform,
            "latency_ms": self.latency_ms,
            "returned_result_count": self.returned_result_count,
            "target_domain_result_count": self.target_domain_result_count,
            "accepted_canonical_result_count": self.accepted_canonical_result_count,
            "duplicate_count": self.duplicate_count,
            "timeout": self.timeout,
            "rate_limited": self.rate_limited,
            "error": self.error,
            "current_state": self.current_state,
            "cooldown_remaining_seconds": self.cooldown_remaining_seconds,
            "historical_performance": self.historical_performance,
        }


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    discovery_id: str
    platform: str
    canonical_url: str
    content_type: ContentType
    indexed_title: str | None
    indexed_snippet: str | None
    discovery_engine: str
    discovery_query: str
    discovered_at: datetime
    query_variant_id: str
    acquisition_mode: AcquisitionMode
    canonical_content_id: str | None
    language_hint: str | None = None
    published_at_hint: datetime | None = None
    metadata_completeness: float = 0
    author_handle: str | None = None
    community: str | None = None
    engines_that_found_it: tuple[str, ...] = ()
    query_variants_that_found_it: tuple[str, ...] = ()
    number_of_independent_discoveries: int = 1
    enrichment_state: str = "not_requested"
    enrichment_metadata: dict[str, Any] = field(default_factory=dict)
    discovery_rrf_score: float = 0.0
    discovery_rounds: tuple[int, ...] = (1,)

    @classmethod
    def from_classification(
        cls,
        classification: ClassifiedUrl,
        *,
        discovery_id: str,
        indexed_title: str | None,
        indexed_snippet: str | None,
        engine: str,
        discovery_query: str,
        query_variant_id: str,
        language_hint: str | None = None,
        published_at_hint: datetime | None = None,
        acquisition_mode: AcquisitionMode = AcquisitionMode.WEB_INDEX,
    ) -> DiscoveryCandidate:
        known = sum(
            value is not None and value != ""
            for value in (
                indexed_title,
                indexed_snippet,
                classification.canonical_content_id,
                language_hint,
                published_at_hint,
                classification.author_handle,
            )
        )
        return cls(
            discovery_id=discovery_id,
            platform=classification.platform,
            canonical_url=classification.canonical_url,
            content_type=classification.content_type,
            indexed_title=indexed_title,
            indexed_snippet=indexed_snippet,
            discovery_engine=engine,
            discovery_query=discovery_query,
            discovered_at=datetime.now(UTC),
            query_variant_id=query_variant_id,
            acquisition_mode=acquisition_mode,
            canonical_content_id=classification.canonical_content_id,
            language_hint=language_hint,
            published_at_hint=published_at_hint,
            metadata_completeness=round(known / 6, 3),
            author_handle=classification.author_handle,
            community=classification.community,
            engines_that_found_it=(engine,),
            query_variants_that_found_it=(query_variant_id,),
        )

    def as_cache_dict(self) -> dict[str, Any]:
        return {
            "discovery_id": self.discovery_id,
            "platform": self.platform,
            "canonical_url": self.canonical_url,
            "content_type": self.content_type.value,
            "indexed_title": self.indexed_title,
            "indexed_snippet": self.indexed_snippet,
            "discovery_engine": self.discovery_engine,
            "discovery_query": self.discovery_query,
            "discovered_at": self.discovered_at.isoformat(),
            "query_variant_id": self.query_variant_id,
            "acquisition_mode": self.acquisition_mode.value,
            "canonical_content_id": self.canonical_content_id,
            "language_hint": self.language_hint,
            "published_at_hint": (
                self.published_at_hint.isoformat() if self.published_at_hint else None
            ),
            "metadata_completeness": self.metadata_completeness,
            "author_handle": self.author_handle,
            "community": self.community,
            "engines_that_found_it": list(self.engines_that_found_it),
            "query_variants_that_found_it": list(self.query_variants_that_found_it),
            "number_of_independent_discoveries": self.number_of_independent_discoveries,
            "enrichment_state": self.enrichment_state,
            "enrichment_metadata": self.enrichment_metadata,
            "discovery_rrf_score": self.discovery_rrf_score,
            "discovery_rounds": list(self.discovery_rounds),
        }

    @classmethod
    def from_cache_dict(cls, value: dict[str, Any]) -> DiscoveryCandidate:
        published = value.get("published_at_hint")
        discovered = value.get("discovered_at")
        return cls(
            discovery_id=str(value["discovery_id"]),
            platform=str(value["platform"]),
            canonical_url=str(value["canonical_url"]),
            content_type=ContentType(str(value["content_type"])),
            indexed_title=value.get("indexed_title"),
            indexed_snippet=value.get("indexed_snippet"),
            discovery_engine=str(value["discovery_engine"]),
            discovery_query=str(value["discovery_query"]),
            discovered_at=datetime.fromisoformat(str(discovered)),
            query_variant_id=str(value["query_variant_id"]),
            acquisition_mode=AcquisitionMode(str(value["acquisition_mode"])),
            canonical_content_id=value.get("canonical_content_id"),
            language_hint=value.get("language_hint"),
            published_at_hint=datetime.fromisoformat(str(published)) if published else None,
            metadata_completeness=float(value.get("metadata_completeness", 0)),
            author_handle=value.get("author_handle"),
            community=value.get("community"),
            engines_that_found_it=tuple(value.get("engines_that_found_it") or ()),
            query_variants_that_found_it=tuple(value.get("query_variants_that_found_it") or ()),
            number_of_independent_discoveries=int(
                value.get("number_of_independent_discoveries", 1)
            ),
            enrichment_state=str(value.get("enrichment_state", "not_requested")),
            enrichment_metadata=dict(value.get("enrichment_metadata") or {}),
            discovery_rrf_score=float(value.get("discovery_rrf_score", 0.0)),
            discovery_rounds=tuple(int(item) for item in value.get("discovery_rounds") or (1,)),
        )


@dataclass(frozen=True, slots=True)
class DiscoverySearchResult:
    candidates: tuple[DiscoveryCandidate, ...]
    telemetry: tuple[EngineTelemetry, ...]
    cache_state: str
    total_latency_ms: float
    returned_count: int
    target_domain_count: int
    canonical_content_count: int
    profile_count: int
    duplicate_count: int
    historical_state: str = "not_requested"

    def diagnostics(self) -> dict[str, Any]:
        return {
            "mode": AcquisitionMode.WEB_INDEX.value,
            "cache_state": self.cache_state,
            "returned": self.returned_count,
            "target_domain_accepted": self.target_domain_count,
            "canonical_posts": self.canonical_content_count,
            "profiles_retained_in_memory": self.profile_count,
            "duplicates": self.duplicate_count,
            "historical_state": self.historical_state,
            "engine_telemetry": [item.as_dict() for item in self.telemetry],
        }
