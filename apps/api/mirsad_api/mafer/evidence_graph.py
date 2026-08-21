from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EvidenceGraphEdge, EvidenceGraphNode


def _bounded(value: str, length: int = 500) -> str:
    return " ".join(value.split())[:length]


class EvidenceGraphRepository:
    """Stores observed provenance relationships; it never infers identity or causality."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def node(
        self,
        node_type: str,
        stable_key: str,
        label: str,
        *,
        properties: dict[str, Any] | None = None,
    ) -> EvidenceGraphNode:
        safe_key = _bounded(stable_key)
        row = self.db.scalar(
            select(EvidenceGraphNode).where(
                EvidenceGraphNode.node_type == node_type,
                EvidenceGraphNode.stable_key == safe_key,
            )
        )
        now = datetime.now(UTC)
        if row is None:
            row = EvidenceGraphNode(
                node_type=node_type,
                stable_key=safe_key,
                label=_bounded(label),
                properties=properties or {},
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(row)
            self.db.flush()
        else:
            row.last_seen_at = now
            row.properties = {**(row.properties or {}), **(properties or {})}
        return row

    def edge(
        self,
        from_node: EvidenceGraphNode,
        to_node: EvidenceGraphNode,
        relationship_type: str,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> EvidenceGraphEdge:
        row = self.db.scalar(
            select(EvidenceGraphEdge).where(
                EvidenceGraphEdge.from_node_id == from_node.id,
                EvidenceGraphEdge.to_node_id == to_node.id,
                EvidenceGraphEdge.relationship_type == relationship_type,
            )
        )
        now = datetime.now(UTC)
        if row is None:
            row = EvidenceGraphEdge(
                from_node_id=from_node.id,
                to_node_id=to_node.id,
                relationship_type=relationship_type,
                evidence=evidence or {},
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(row)
        else:
            row.support_count += 1
            row.last_seen_at = now
            row.evidence = {**(row.evidence or {}), **(evidence or {})}
        return row

    def observe_result(
        self,
        *,
        query: str,
        content_public_id: str,
        canonical_url: str,
        source: str,
        author_handle: str | None,
        hashtags: list[str] | None,
        cluster_id: str | None,
        session_id: str,
    ) -> int:
        query_node = self.node("query", query.casefold(), query)
        content_node = self.node("content", content_public_id, content_public_id)
        url_key = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        url_node = self.node("canonical_url", url_key, canonical_url)
        source_node = self.node("source", source, source)
        self.edge(query_node, content_node, "discovered_by", evidence={"session_id": session_id})
        self.edge(content_node, url_node, "links_to")
        self.edge(content_node, source_node, "published_on")
        count = 3
        if author_handle:
            handle_node = self.node("author_handle", author_handle.casefold(), author_handle)
            self.edge(content_node, handle_node, "mentions_author")
            count += 1
        for hashtag in (hashtags or [])[:20]:
            hashtag_node = self.node("hashtag", hashtag.casefold(), hashtag)
            self.edge(content_node, hashtag_node, "mentions")
            count += 1
        if cluster_id:
            story_node = self.node("story", cluster_id, cluster_id)
            self.edge(content_node, story_node, "same_story", evidence={"algorithmic": True})
            count += 1
        return count
