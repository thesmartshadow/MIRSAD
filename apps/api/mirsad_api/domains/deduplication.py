from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .query import normalize_text, tokenize

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    if port and not (
        (parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
        )
    )
    return urlunsplit(((parts.scheme or "https").lower(), host, path, query, ""))


def content_fingerprint(title: str | None, text: str) -> str:
    normalized = normalize_text(f"{title or ''} {text}")
    normalized = re.sub(r"[^\w\s\u0600-\u06ff]", "", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def text_similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = set(tokenize(left)), set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


@dataclass(frozen=True, slots=True)
class DeduplicationItem:
    key: int
    source: str
    canonical_url: str
    title: str | None
    text: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class DuplicateSet:
    members: tuple[int, ...]
    similarities: dict[int, float]
    stages: dict[int, str]
    sources: tuple[str, ...]
    earliest_seen: datetime | None
    latest_seen: datetime | None


def find_duplicate_groups(
    items: list[DeduplicationItem], *, similarity_threshold: float = 0.78
) -> list[DuplicateSet]:
    parent = {item.key: item.key for item in items}
    similarity: dict[int, float] = {item.key: 1.0 for item in items}
    stages: dict[int, str] = {item.key: "canonical" for item in items}

    def find(key: int) -> int:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    fingerprints = {item.key: content_fingerprint(item.title, item.text) for item in items}
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            stage: str | None = None
            if canonicalize_url(left.canonical_url) == canonicalize_url(right.canonical_url):
                stage = "url"
            elif fingerprints[left.key] == fingerprints[right.key]:
                stage = "fingerprint"
            if stage:
                union(left.key, right.key)
                similarity[right.key] = 1.0
                stages[right.key] = stage

    exact_groups: dict[int, list[DeduplicationItem]] = {}
    for item in items:
        exact_groups.setdefault(find(item.key), []).append(item)

    # Near-duplicate admission uses complete linkage to avoid transitive false merges.
    grouped: list[list[DeduplicationItem]] = []
    ordered_components = sorted(
        exact_groups.values(), key=lambda group: min(item.key for item in group)
    )
    for component in ordered_components:
        destination = next(
            (
                group
                for group in grouped
                if all(
                    text_similarity(
                        f"{left.title or ''} {left.text}",
                        f"{right.title or ''} {right.text}",
                    )
                    >= similarity_threshold
                    for left in component
                    for right in group
                )
            ),
            None,
        )
        if destination is None:
            grouped.append(component[:])
            continue
        for member in component:
            member_score = min(
                text_similarity(
                    f"{member.title or ''} {member.text}",
                    f"{existing.title or ''} {existing.text}",
                )
                for existing in destination
            )
            similarity[member.key] = member_score
            stages[member.key] = "similarity"
        destination.extend(component)

    output: list[DuplicateSet] = []
    for members in grouped:
        if len(members) < 2:
            continue
        dates = [item.published_at for item in members if item.published_at]
        output.append(
            DuplicateSet(
                members=tuple(item.key for item in members),
                similarities={item.key: similarity[item.key] for item in members},
                stages={item.key: stages[item.key] for item in members},
                sources=tuple(sorted({item.source for item in members})),
                earliest_seen=min(dates) if dates else None,
                latest_seen=max(dates) if dates else None,
            )
        )
    return output


def cross_source_score(source_count: int) -> float:
    if source_count <= 1:
        return 0.0
    return round(min(100, 40 + 20 * (source_count - 2)), 2)
