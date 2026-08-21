from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from dataclasses import replace
from time import perf_counter
from typing import TYPE_CHECKING, Any

from ..domains.query import process_query
from ..mafer.fusion import DiscoveryRankObservation, weighted_reciprocal_rank_fusion
from ..provenance import AcquisitionMode
from .classifiers import ContentType, classify_platform_url
from .common_crawl import CommonCrawlAdapter
from .enrichment import OfficialEmbedEnricher
from .models import DiscoveryCandidate, DiscoverySearchResult, EngineTelemetry
from .repository import DiscoveryRepository
from .searxng import DiscoveryProviderError, SearxngClient, SearxResponse

if TYPE_CHECKING:
    from ..connectors.base import ConnectorItem

PLATFORM_SITE_QUERIES = {
    "x": "(site:x.com OR site:twitter.com)",
    "threads": "(site:threads.com OR site:threads.net)",
    "reddit": "site:reddit.com",
}


class WebSocialDiscoveryService:
    def __init__(
        self,
        *,
        enabled: bool,
        client: SearxngClient | None,
        repository: DiscoveryRepository | None = None,
        cache_ttl_seconds: int = 900,
        variant_limit: int = 2,
        embed_enricher: OfficialEmbedEnricher | None = None,
        common_crawl: CommonCrawlAdapter | None = None,
    ) -> None:
        self.enabled = enabled and client is not None
        self.client = client
        self.repository = repository
        self.cache_ttl_seconds = max(30, min(cache_ttl_seconds, 86400))
        self.variant_limit = max(1, min(variant_limit, 3))
        self.embed_enricher = embed_enricher or OfficialEmbedEnricher(enabled=False)
        self.common_crawl = common_crawl
        self._health_result: tuple[bool, str, float] | None = None
        self._health_checked_at = 0.0
        self._health_lock = asyncio.Lock()

    async def validate_access(self, platform: str) -> tuple[bool, str, float]:
        if not self.enabled or self.client is None:
            return False, "unconfigured", 0
        if platform not in PLATFORM_SITE_QUERIES:
            return False, "unsupported_platform", 0
        async with self._health_lock:
            now = perf_counter()
            if self._health_result and now - self._health_checked_at < 30:
                return self._health_result
            self._health_result = await self.client.health_check()
            self._health_checked_at = perf_counter()
            return self._health_result

    async def search(
        self,
        platform: str,
        query: str,
        *,
        limit: int,
        language: str = "all",
        time_scope: str = "all",
        exact_phrase: bool = False,
        historical: bool = False,
        original_query: str | None = None,
        query_variants: tuple[str, ...] = (),
        query_variant_metadata: tuple[dict[str, Any], ...] = (),
        search_round: int = 1,
        max_engine_calls: int = 0,
        max_discovered_urls: int = 0,
        max_historical_calls: int = -1,
    ) -> DiscoverySearchResult:
        if not self.enabled or self.client is None:
            raise DiscoveryProviderError(
                "configuration_missing", "Local SearXNG web discovery is not configured"
            )
        if platform not in PLATFORM_SITE_QUERIES:
            raise DiscoveryProviderError(
                "unsupported_platform", "Platform is not supported by web discovery"
            )
        started = perf_counter()
        processed = process_query(original_query or query, exact_phrase=exact_phrase)
        metadata_by_text = {
            str(item.get("text", "")).strip(): item
            for item in query_variant_metadata
            if isinstance(item, dict) and str(item.get("text", "")).strip()
        }
        variant_values = list(query_variants or processed.variants or (processed.normalized,))
        variants: list[tuple[str, str, float]] = []
        for index, value in enumerate(
            dict.fromkeys(item.strip() for item in variant_values if item.strip())
        ):
            item = metadata_by_text.get(value, {})
            fallback_id = hashlib.sha256(f"{index}:{value}".encode()).hexdigest()[:16]
            variant_id = str(item.get("variant_id") or fallback_id)
            confidence = max(0.0, min(float(item.get("confidence", 1.0)), 1.0))
            variants.append((variant_id, value, confidence))
            if len(variants) >= self.variant_limit:
                break
        if not variants:
            variants = [(hashlib.sha256(query.encode()).hexdigest()[:16], query, 1.0)]
        if max_engine_calls > 0:
            engine_count = max(1, len(self.client.engines))
            variants = variants[: max(1, max_engine_calls // engine_count)]
        if exact_phrase:
            variant_id, value, confidence = variants[0]
            variants[0] = (variant_id, f'"{value.strip(chr(34))}"', confidence)
        cache_parts = {
            "query": processed.normalized,
            "variants": "|".join(
                f"{identifier}:{value}:{confidence}" for identifier, value, confidence in variants
            ),
            "platform": platform,
            "language": language,
            "time_scope": time_scope,
            "engines": ",".join(self.client.engines),
            "limit": min(limit, max_discovered_urls or 100, 100),
            "historical": historical and max_historical_calls != 0,
        }
        cache_key = DiscoveryRepository.cache_key(cache_parts)
        cached_payload: dict[str, Any] | None = None
        cache_state = "fresh"
        if self.repository:
            cached_payload, cache_state = self.repository.get_cache(cache_key)
            if cached_payload is not None and cache_state == "cached":
                return self._result_from_cache(cached_payload, cache_state)

        constrained_queries = [
            (
                variant_id,
                f"{PLATFORM_SITE_QUERIES[platform]} {variant}",
                confidence,
            )
            for variant_id, variant, confidence in variants
        ]
        engines_per_query = (
            max(1, max_engine_calls // len(constrained_queries)) if max_engine_calls > 0 else 0
        )
        time_range = self._searx_time_range(time_scope)
        historical_performance = (
            self.repository.engine_performance(platform) if self.repository else {}
        )
        preferred_engines = tuple(
            sorted(
                self.client.engines,
                key=lambda engine: (
                    -self._engine_discovery_weight(historical_performance.get(engine, {})),
                    engine,
                ),
            )
        )
        try:
            responses = await asyncio.gather(
                *(
                    self.client.search(
                        constrained_query,
                        language=language,
                        time_range=time_range,
                        max_engines=engines_per_query,
                        preferred_engines=preferred_engines,
                    )
                    for _variant_id, constrained_query, _confidence in constrained_queries
                )
            )
        except DiscoveryProviderError:
            if cached_payload is not None and cache_state == "stale":
                return self._result_from_cache(cached_payload, "stale_fallback")
            raise

        candidates, telemetry, counts = self._validate_results(
            platform,
            constrained_queries,
            responses,
            search_round=search_round,
            engine_weights={
                engine: self._engine_discovery_weight(values)
                for engine, values in historical_performance.items()
            },
        )
        states = self.client.engine_states()
        telemetry = [
            replace(
                item,
                current_state=str(states.get(item.engine, {}).get("state", "UNKNOWN")),
                cooldown_remaining_seconds=float(
                    states.get(item.engine, {}).get("cooldown_remaining_seconds", 0.0)
                ),
            )
            for item in telemetry
        ]
        if self.repository:
            self.repository.record_engine_telemetry(telemetry)
            performance = self.repository.engine_performance(platform)
            telemetry = [
                replace(
                    item,
                    historical_performance=performance.get(item.engine, {}),
                )
                for item in telemetry
            ]
        historical_state = (
            "budget_ineligible" if historical and max_historical_calls == 0 else "not_requested"
        )
        if historical and max_historical_calls != 0:
            historical_state = await self._historical_lookup_state(
                platform, original_query or query
            )

        all_candidates = list(candidates.values())
        if self.embed_enricher.enabled:
            enriched = await asyncio.gather(
                *(
                    self.embed_enricher.enrich(platform, item.canonical_url)
                    for item in all_candidates
                )
            )
            all_candidates = [
                replace(
                    candidate,
                    enrichment_state=enrichment.state,
                    enrichment_metadata=enrichment.metadata,
                    indexed_title=(
                        candidate.indexed_title
                        or (
                            str(enrichment.metadata.get("title"))
                            if enrichment.metadata.get("title")
                            else None
                        )
                    ),
                )
                for candidate, enrichment in zip(all_candidates, enriched, strict=True)
            ]

        if self.repository:
            for candidate in all_candidates:
                self.repository.remember(candidate)
            supported: list[DiscoveryCandidate] = []
            for candidate in all_candidates:
                engines, support_variants, independent = self.repository.support_for(
                    candidate.canonical_url
                )
                supported.append(
                    replace(
                        candidate,
                        engines_that_found_it=engines or candidate.engines_that_found_it,
                        query_variants_that_found_it=(
                            support_variants or candidate.query_variants_that_found_it
                        ),
                        number_of_independent_discoveries=max(
                            independent, candidate.number_of_independent_discoveries
                        ),
                    )
                )
            all_candidates = supported

        content_candidates = tuple(
            sorted(
                (
                    item
                    for item in all_candidates
                    if item.content_type in {ContentType.POST, ContentType.COMMENT}
                ),
                key=lambda item: (
                    -item.discovery_rrf_score,
                    -item.number_of_independent_discoveries,
                    -item.metadata_completeness,
                    item.canonical_url,
                ),
            )[: min(limit, max_discovered_urls or 100, 100)]
        )
        result = DiscoverySearchResult(
            content_candidates,
            tuple(telemetry),
            "refreshed" if cache_state == "stale" else "fresh",
            (perf_counter() - started) * 1000,
            counts["returned"],
            counts["target_domain"],
            len(content_candidates),
            counts["profiles"],
            counts["duplicates"],
            historical_state,
        )
        if self.repository:
            self.repository.put_cache(
                cache_key,
                platform,
                self._result_to_cache(result),
                ttl_seconds=self.cache_ttl_seconds,
            )
        return result

    @staticmethod
    def to_connector_items(result: DiscoverySearchResult) -> list[ConnectorItem]:
        from ..connectors.base import ConnectorItem

        items: list[ConnectorItem] = []
        for candidate in result.candidates:
            text = candidate.indexed_snippet or candidate.indexed_title or ""
            title = candidate.indexed_title
            if not text and not title:
                continue
            source_type = candidate.content_type.value
            external_id = (
                candidate.canonical_content_id
                or hashlib.sha256(candidate.canonical_url.encode()).hexdigest()
            )
            items.append(
                ConnectorItem(
                    source=candidate.platform,
                    external_id=external_id,
                    canonical_url=candidate.canonical_url,
                    author=candidate.enrichment_metadata.get("author_name"),
                    author_handle=candidate.author_handle,
                    title=title,
                    text=text,
                    published_at=candidate.published_at_hint,
                    language=candidate.language_hint or "und",
                    media_type="post" if source_type == "post" else source_type,
                    raw_metrics={},
                    raw_metadata={
                        "source_type": source_type,
                        "acquisition_mode": candidate.acquisition_mode.value,
                        "indexed_public_web_coverage": True,
                        "direct_platform_api": False,
                        "discovery_id": candidate.discovery_id,
                        "discovery_engine": candidate.discovery_engine,
                        "discovery_query": candidate.discovery_query,
                        "query_variant_id": candidate.query_variant_id,
                        "engines_that_found_it": list(candidate.engines_that_found_it),
                        "query_variants_that_found_it": list(
                            candidate.query_variants_that_found_it
                        ),
                        "discovery_support": candidate.number_of_independent_discoveries,
                        "metadata_completeness": candidate.metadata_completeness,
                        "evidence_completeness": (
                            "RICH"
                            if candidate.metadata_completeness >= 0.75
                            else "MODERATE"
                            if candidate.metadata_completeness >= 0.45
                            else "SPARSE"
                        ),
                        "discovery_rrf_score": candidate.discovery_rrf_score,
                        "discovery_rounds": list(candidate.discovery_rounds),
                        "community": candidate.community,
                        "enrichment_state": candidate.enrichment_state,
                        "enrichment_acquisition_mode": AcquisitionMode.OFFICIAL_EMBED.value,
                        "enrichment_metadata": candidate.enrichment_metadata,
                    },
                    acquisition_mode=AcquisitionMode.WEB_INDEX,
                )
            )
        return items

    @staticmethod
    def _validate_results(
        platform: str,
        queries: list[tuple[str, str, float]],
        responses: list[SearxResponse],
        *,
        search_round: int = 1,
        engine_weights: dict[str, float] | None = None,
    ) -> tuple[dict[str, DiscoveryCandidate], list[EngineTelemetry], dict[str, int]]:
        from ..connectors.base import parse_datetime

        candidates: dict[str, DiscoveryCandidate] = {}
        telemetry_values: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "returned": 0,
                "target": 0,
                "accepted": 0,
                "duplicates": 0,
                "latency": None,
            }
        )
        counts = {"returned": 0, "target_domain": 0, "profiles": 0, "duplicates": 0}
        accepted_by_engine: set[tuple[str, str, str]] = set()
        rank_observations: list[DiscoveryRankObservation] = []
        for (variant_id, constrained_query, variant_confidence), response in zip(
            queries, responses, strict=True
        ):
            counts["returned"] += len(response.results)
            for rank, row in enumerate(response.results, 1):
                classification = classify_platform_url(platform, row.url)
                for engine in row.engines:
                    values = telemetry_values[(engine, variant_id)]
                    values["returned"] += 1
                    values["latency"] = response.latency_ms
                    if classification is not None:
                        values["target"] += 1
                if classification is None:
                    continue
                counts["target_domain"] += 1
                if classification.content_type == ContentType.PROFILE:
                    counts["profiles"] += 1
                if classification.content_type == ContentType.OTHER:
                    continue
                for found_engine in row.engines:
                    acceptance_key = (
                        found_engine,
                        variant_id,
                        classification.canonical_url,
                    )
                    if acceptance_key not in accepted_by_engine:
                        telemetry_values[(found_engine, variant_id)]["accepted"] += 1
                        accepted_by_engine.add(acceptance_key)
                    rank_observations.append(
                        DiscoveryRankObservation(
                            classification.canonical_url,
                            found_engine,
                            variant_id,
                            rank,
                            engine_weight=(engine_weights or {}).get(found_engine, 1.0),
                            variant_confidence=variant_confidence,
                            round_number=search_round,
                        )
                    )
                published = parse_datetime(row.published_at)
                engine = row.engines[0]
                discovery_id = hashlib.sha256(
                    f"{platform}:{classification.canonical_url}".encode()
                ).hexdigest()
                candidate = DiscoveryCandidate.from_classification(
                    classification,
                    discovery_id=discovery_id,
                    indexed_title=row.title,
                    indexed_snippet=row.snippet,
                    engine=engine,
                    discovery_query=constrained_query,
                    query_variant_id=variant_id,
                    language_hint=row.language,
                    published_at_hint=published,
                )
                existing = candidates.get(classification.canonical_url)
                if existing is not None:
                    counts["duplicates"] += 1
                    for found_engine in row.engines:
                        telemetry_values[(found_engine, variant_id)]["duplicates"] += 1
                    candidates[classification.canonical_url] = replace(
                        existing,
                        indexed_title=existing.indexed_title or candidate.indexed_title,
                        indexed_snippet=existing.indexed_snippet or candidate.indexed_snippet,
                        engines_that_found_it=tuple(
                            sorted(set(existing.engines_that_found_it).union(row.engines))
                        ),
                        query_variants_that_found_it=tuple(
                            sorted(set(existing.query_variants_that_found_it).union({variant_id}))
                        ),
                        number_of_independent_discoveries=len(
                            set(existing.engines_that_found_it).union(row.engines)
                        ),
                        discovery_rounds=tuple(
                            sorted(set(existing.discovery_rounds).union({search_round}))
                        ),
                    )
                else:
                    candidates[classification.canonical_url] = replace(
                        candidate,
                        engines_that_found_it=row.engines,
                        query_variants_that_found_it=(variant_id,),
                        number_of_independent_discoveries=len(row.engines),
                        discovery_rounds=(search_round,),
                    )
            for engine, reason in (*response.unresponsive_engines, *response.skipped_engines):
                values = telemetry_values[(engine, variant_id)]
                values["error"] = reason
                lowered = reason.casefold()
                values["timeout"] = "timeout" in lowered
                values["rate_limited"] = (
                    "429" in lowered or "rate" in lowered or "too many requests" in lowered
                )
        fused = {
            item.canonical_url: item for item in weighted_reciprocal_rank_fusion(rank_observations)
        }
        for canonical_url, candidate in tuple(candidates.items()):
            score = fused.get(canonical_url)
            if score is None:
                continue
            candidates[canonical_url] = replace(
                candidate,
                discovery_rrf_score=score.score,
                engines_that_found_it=score.engines,
                query_variants_that_found_it=score.variants,
                number_of_independent_discoveries=score.independent_support,
                discovery_rounds=score.rounds,
            )
        telemetry = [
            EngineTelemetry(
                engine=engine,
                query_variant_id=variant_id,
                target_platform=platform,
                latency_ms=values.get("latency"),
                returned_result_count=values["returned"],
                target_domain_result_count=values["target"],
                accepted_canonical_result_count=values["accepted"],
                duplicate_count=values["duplicates"],
                timeout=bool(values.get("timeout")),
                rate_limited=bool(values.get("rate_limited")),
                error=values.get("error"),
            )
            for (engine, variant_id), values in sorted(telemetry_values.items())
        ]
        return candidates, telemetry, counts

    @staticmethod
    def _engine_discovery_weight(values: dict[str, float | str]) -> float:
        if not values or not values.get("request_count"):
            return 1.0
        precision = max(0.0, min(float(values.get("target_domain_precision", 0)), 1.0))
        canonical_yield = max(0.0, min(float(values.get("canonical_yield", 0)), 1.0))
        failure_rate = max(
            0.0,
            min(
                float(values.get("timeout_rate", 0)) + float(values.get("rate_limit_rate", 0)),
                1.0,
            ),
        )
        quality = 0.45 * precision + 0.35 * canonical_yield + 0.2 * (1 - failure_rate)
        return round(0.75 + 0.25 * quality, 4)

    async def _historical_lookup_state(self, platform: str, query: str) -> str:
        if self.common_crawl is None:
            return "unconfigured"
        classification = classify_platform_url(platform, query)
        if classification is None or not classification.is_content:
            return "url_required"
        try:
            lookup = await self.common_crawl.lookup(platform, classification.canonical_url)
        except DiscoveryProviderError as exc:
            return exc.code
        return f"captures:{len(lookup.captures)}"

    @staticmethod
    def _searx_time_range(value: str) -> str | None:
        return {"24h": "day", "30d": "month"}.get(value)

    @staticmethod
    def _result_to_cache(result: DiscoverySearchResult) -> dict[str, Any]:
        return {
            "candidates": [item.as_cache_dict() for item in result.candidates],
            "telemetry": [item.as_dict() for item in result.telemetry],
            "total_latency_ms": result.total_latency_ms,
            "returned_count": result.returned_count,
            "target_domain_count": result.target_domain_count,
            "canonical_content_count": result.canonical_content_count,
            "profile_count": result.profile_count,
            "duplicate_count": result.duplicate_count,
            "historical_state": result.historical_state,
        }

    @staticmethod
    def _result_from_cache(payload: dict[str, Any], state: str) -> DiscoverySearchResult:
        telemetry = tuple(
            EngineTelemetry(
                engine=str(row["engine"]),
                query_variant_id=str(row["query_variant_id"]),
                target_platform=str(row["target_platform"]),
                latency_ms=(
                    float(row["latency_ms"]) if row.get("latency_ms") is not None else None
                ),
                returned_result_count=int(row.get("returned_result_count", 0)),
                target_domain_result_count=int(row.get("target_domain_result_count", 0)),
                accepted_canonical_result_count=int(row.get("accepted_canonical_result_count", 0)),
                duplicate_count=int(row.get("duplicate_count", 0)),
                timeout=bool(row.get("timeout", False)),
                rate_limited=bool(row.get("rate_limited", False)),
                error=row.get("error"),
                current_state=str(row.get("current_state", "UNKNOWN")),
                cooldown_remaining_seconds=float(row.get("cooldown_remaining_seconds", 0.0)),
                historical_performance=dict(row.get("historical_performance") or {}),
            )
            for row in payload.get("telemetry", [])
            if isinstance(row, dict)
        )
        return DiscoverySearchResult(
            tuple(
                DiscoveryCandidate.from_cache_dict(row)
                for row in payload.get("candidates", [])
                if isinstance(row, dict)
            ),
            telemetry,
            state,
            float(payload.get("total_latency_ms", 0)),
            int(payload.get("returned_count", 0)),
            int(payload.get("target_domain_count", 0)),
            int(payload.get("canonical_content_count", 0)),
            int(payload.get("profile_count", 0)),
            int(payload.get("duplicate_count", 0)),
            str(payload.get("historical_state", "not_requested")),
        )
