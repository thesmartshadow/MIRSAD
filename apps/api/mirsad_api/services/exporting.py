from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from .read_models import get_search_response

EXPORT_VERSION = "1.0"


def _spreadsheet_safe(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def build_export(db: Session, session_id: str) -> dict[str, Any]:
    response = get_search_response(db, session_id)
    cluster_by_item = {
        member_id: cluster.id for cluster in response.clusters for member_id in cluster.member_ids
    }
    return {
        "schema": "mirsad.search-export",
        "version": EXPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "search": response.session.model_dump(mode="json"),
        "analytics": response.analytics,
        "records": [
            {
                "query": response.session.original_query,
                "source": item.source,
                "source_type": item.source_type,
                "acquisition_mode": item.acquisition_mode,
                "acquisition_modes_seen": item.acquisition_modes_seen,
                "indexed_public_web_coverage": item.indexed_public_web_coverage,
                "discovery_support": item.discovery_support,
                "discovery_engines": item.discovery_engines,
                "evidence_completeness": item.evidence_completeness,
                "evidence_completeness_score": item.evidence_completeness_score,
                "author": item.author,
                "author_handle": item.author_handle,
                "author_verified": item.author_verified,
                "title": item.title,
                "text": item.text,
                "language": item.language,
                "hashtags": item.hashtags,
                "mentions": item.mentions,
                "media_type": item.media_type,
                "like_count": item.like_count,
                "view_count": item.view_count,
                "comment_count": item.comment_count,
                "share_count": item.share_count,
                "repost_count": item.repost_count,
                "reaction_count": item.reaction_count,
                "publication_time": item.published_at.isoformat() if item.published_at else None,
                "fetch_time": item.fetched_at.isoformat(),
                "original_url": item.canonical_url,
                "final_score": item.explanation.final_score,
                "relevance": item.explanation.relevance,
                "freshness": item.explanation.freshness,
                "engagement": item.explanation.engagement,
                "social_reach": item.social_reach,
                "source_confidence": item.explanation.source_confidence,
                "cross_source_presence": item.explanation.cross_source_presence,
                "duplicate_group": item.duplicate_group_id,
                "cluster": cluster_by_item.get(item.id),
            }
            for item in response.results
        ],
    }


def export_csv(payload: dict[str, Any]) -> bytes:
    fields = [
        "query",
        "source",
        "source_type",
        "acquisition_mode",
        "acquisition_modes_seen",
        "indexed_public_web_coverage",
        "discovery_support",
        "discovery_engines",
        "evidence_completeness",
        "evidence_completeness_score",
        "author",
        "author_handle",
        "author_verified",
        "title",
        "text",
        "language",
        "hashtags",
        "mentions",
        "media_type",
        "like_count",
        "view_count",
        "comment_count",
        "share_count",
        "repost_count",
        "reaction_count",
        "publication_time",
        "fetch_time",
        "original_url",
        "final_score",
        "relevance",
        "freshness",
        "engagement",
        "social_reach",
        "source_confidence",
        "cross_source_presence",
        "duplicate_group",
        "cluster",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(
        {key: _spreadsheet_safe(value) for key, value in record.items()}
        for record in payload["records"]
    )
    return output.getvalue().encode("utf-8-sig")
