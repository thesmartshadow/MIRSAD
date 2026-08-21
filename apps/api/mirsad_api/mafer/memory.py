from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..connectors.base import ConnectorItem
from ..domains.query import ProcessedQuery, fts_query, process_query
from ..domains.ranking import is_candidate_match
from ..models import ContentItem, ContentMetric, DiscoveryRecord, Source
from ..provenance import AcquisitionMode
from .lattice import QueryLattice


@dataclass(frozen=True, slots=True)
class LocalMemoryResult:
    items: tuple[ConnectorItem, ...]
    content_fts_matches: int
    discovery_memory_matches: int
    scanned_discovery_records: int

    def as_dict(self) -> dict[str, int]:
        return {
            "content_fts_matches": self.content_fts_matches,
            "discovery_memory_matches": self.discovery_memory_matches,
            "scanned_discovery_records": self.scanned_discovery_records,
            "total_local_candidates": len(self.items),
        }


class LocalMemorySearch:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        processed: ProcessedQuery,
        lattice: QueryLattice,
        *,
        limit: int,
    ) -> LocalMemoryResult:
        bounded = max(1, min(limit, 200))
        content_ids: list[int] = []
        for variant in lattice.variants:
            if variant.drift_risk > 0.35 or len(content_ids) >= bounded:
                continue
            variant_query = process_query(
                variant.text,
                exact_phrase=variant.transformation.value == "EXACT",
            )
            for item_id in self._fts_content_ids(variant_query, bounded):
                if item_id not in content_ids:
                    content_ids.append(item_id)
                if len(content_ids) >= bounded:
                    break
        content_rows = self.db.execute(
            select(ContentItem, Source, ContentMetric)
            .join(Source, Source.id == ContentItem.source_id)
            .outerjoin(ContentMetric, ContentMetric.content_item_id == ContentItem.id)
            .where(ContentItem.id.in_(content_ids or [-1]))
        ).all()
        order = {item_id: index for index, item_id in enumerate(content_ids)}
        content_rows.sort(key=lambda row: order.get(row[0].id, bounded))
        output = [
            self._content_connector_item(item, source, metric)
            for item, source, metric in content_rows
        ]
        seen_urls = {item.canonical_url for item in output}

        discovery_rows = self.db.scalars(
            select(DiscoveryRecord)
            .order_by(DiscoveryRecord.last_seen_at.desc(), DiscoveryRecord.id.asc())
            .limit(min(1000, bounded * 10))
        ).all()
        discovery_matches = 0
        variant_queries = tuple(
            process_query(variant.text, exact_phrase=variant.transformation.value == "EXACT")
            for variant in lattice.variants
            if variant.drift_risk <= 0.35
        )
        for record in discovery_rows:
            if len(output) >= bounded or record.canonical_url in seen_urls:
                continue
            if not any(
                is_candidate_match(
                    variant,
                    record.indexed_title,
                    record.indexed_snippet or "",
                    canonical_url=record.canonical_url,
                )
                for variant in variant_queries
            ):
                continue
            output.append(self._discovery_connector_item(record))
            seen_urls.add(record.canonical_url)
            discovery_matches += 1
        return LocalMemoryResult(
            tuple(output[:bounded]),
            len(content_rows),
            discovery_matches,
            len(discovery_rows),
        )

    def _fts_content_ids(self, processed: ProcessedQuery, limit: int) -> list[int]:
        if not processed.tokens:
            return []
        rows = self.db.execute(
            text(
                "SELECT rowid FROM content_fts WHERE content_fts MATCH :query "
                "ORDER BY bm25(content_fts, 4.0, 1.0, 0.5, 4.0, 1.0, 0.5), rowid "
                "LIMIT :limit"
            ),
            {"query": fts_query(processed), "limit": limit},
        ).all()
        return [int(row.rowid) for row in rows]

    @staticmethod
    def _content_connector_item(
        item: ContentItem, source: Source, metric: ContentMetric | None
    ) -> ConnectorItem:
        try:
            acquisition = AcquisitionMode(item.acquisition_mode)
        except ValueError:
            acquisition = AcquisitionMode.MANUAL_IMPORT
        metadata = dict(item.raw_metadata or {})
        metadata["local_memory_reuse"] = True
        return ConnectorItem(
            source=source.key,
            external_id=item.external_id,
            canonical_url=item.canonical_url,
            author=item.author,
            author_handle=item.author_handle,
            author_verified=item.author_verified,
            title=item.title,
            text=item.text,
            published_at=item.published_at,
            fetched_at=item.fetched_at,
            language=item.language,
            hashtags=tuple(item.hashtags) if item.hashtags is not None else None,
            mentions=tuple(item.mentions) if item.mentions is not None else None,
            media_type=item.media_type,
            raw_metrics=dict(metric.raw_metrics or {}) if metric else {},
            raw_metadata=metadata,
            acquisition_mode=acquisition,
        )

    @staticmethod
    def _discovery_connector_item(record: DiscoveryRecord) -> ConnectorItem:
        try:
            acquisition = AcquisitionMode(record.acquisition_mode)
        except ValueError:
            acquisition = AcquisitionMode.WEB_INDEX
        return ConnectorItem(
            source=record.platform,
            external_id=record.canonical_content_id or record.public_id,
            canonical_url=record.canonical_url,
            author=None,
            title=record.indexed_title,
            text=record.indexed_snippet or record.indexed_title or "",
            published_at=record.published_at_hint,
            fetched_at=record.last_seen_at,
            language=record.language_hint or "und",
            raw_metrics={},
            raw_metadata={
                "source_type": record.content_type,
                "local_memory_reuse": True,
                "indexed_public_web_coverage": acquisition == AcquisitionMode.WEB_INDEX,
                "metadata_completeness": record.metadata_completeness,
                "availability_state": record.availability_state,
                "first_seen_by_mirsad": record.first_seen_at.isoformat(),
                "last_seen_by_mirsad": record.last_seen_at.isoformat(),
            },
            acquisition_mode=acquisition,
        )
