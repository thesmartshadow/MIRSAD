from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations

from .deduplication import DeduplicationItem, canonicalize_url
from .query import detect_language, normalize_text, token_sequence

STOP_WORDS = {
    "a",
    "about",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "new",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "example",
    "الى",
    "أن",
    "ان",
    "بعد",
    "عن",
    "على",
    "علي",
    "في",
    "كان",
    "كما",
    "من",
    "هذا",
    "هذه",
    "و",
}

LATIN_ENTITY = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*\b")
MAX_BLOCK_SIZE = 32
MAX_CANDIDATES_PER_ITEM = 24
MAX_TEMPORAL_NEIGHBORS = 12
SEMANTIC_STORY_THRESHOLD = 0.79
LONG_GAP_SEMANTIC_THRESHOLD = 0.88


@dataclass(frozen=True, slots=True)
class TopicCluster:
    members: tuple[int, ...]
    representative_title: str
    source_distribution: dict[str, int]
    earliest_at: datetime | None
    latest_at: datetime | None
    terms: tuple[str, ...]
    member_similarities: dict[int, float] = field(default_factory=dict)
    member_reasons: dict[int, tuple[str, ...]] = field(default_factory=dict)
    suspicious: bool = False
    suspicious_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ClusterDocumentFeatures:
    key: int
    title_tokens: frozenset[str]
    body_tokens: frozenset[str]
    all_tokens: frozenset[str]
    distinctive_tokens: frozenset[str]
    identity_tokens: frozenset[str]
    entity_tokens: frozenset[str]
    title_phrases: frozenset[tuple[str, str]]
    language: str


@dataclass(frozen=True, slots=True)
class ClusterCandidatePlan:
    pairs: tuple[tuple[int, int], ...]
    representative_keys: tuple[int, ...]
    components: dict[int, tuple[int, ...]]
    features: dict[int, ClusterDocumentFeatures]
    token_weights: dict[str, float]
    query_tokens: frozenset[str]
    lexical_block_pairs: int
    temporal_block_pairs: int
    capped_pairs: int


@dataclass(frozen=True, slots=True)
class ClusterPairEvidence:
    match: bool
    score: float
    lexical_similarity: float
    title_similarity: float
    body_similarity: float
    semantic_similarity: float | None
    temporal_proximity: float
    shared_distinctive_terms: tuple[str, ...]
    shared_story_identifiers: tuple[str, ...]
    shared_entities: tuple[str, ...]
    shared_title_phrases: tuple[str, ...]
    reasons: tuple[str, ...]


def _meaningful_sequence(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in token_sequence(value)
        if len(token) > 2 and token not in STOP_WORDS
    )


def _phrases(tokens: tuple[str, ...]) -> frozenset[tuple[str, str]]:
    return frozenset(zip(tokens, tokens[1:], strict=False))


def _union_find_components(
    items: list[DeduplicationItem], duplicate_groups: Iterable[Iterable[int]]
) -> tuple[dict[int, tuple[int, ...]], dict[int, int]]:
    parent = {item.key: item.key for item in items}

    def find(key: int) -> int:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    by_url: dict[str, list[int]] = defaultdict(list)
    for item in items:
        by_url[canonicalize_url(item.canonical_url)].append(item.key)
    for keys in by_url.values():
        for key in keys[1:]:
            union(keys[0], key)
    valid_keys = set(parent)
    for group in duplicate_groups:
        keys = sorted(set(group) & valid_keys)
        for key in keys[1:]:
            union(keys[0], key)

    grouped: dict[int, list[int]] = defaultdict(list)
    for key in sorted(parent):
        grouped[find(key)].append(key)
    components = {min(keys): tuple(sorted(keys)) for keys in grouped.values()}
    component_by_key = {
        key: representative for representative, keys in components.items() for key in keys
    }
    return components, component_by_key


def _representative(
    members: tuple[int, ...], by_key: Mapping[int, DeduplicationItem]
) -> int:
    return max(
        members,
        key=lambda key: (
            len(_meaningful_sequence(f"{by_key[key].title or ''} {by_key[key].text}")),
            bool(by_key[key].title),
            -key,
        ),
    )


def _extract_entities(value: str, query_tokens: frozenset[str]) -> frozenset[str]:
    return frozenset(
        normalize_text(match.group(0))
        for match in LATIN_ENTITY.finditer(value)
        if len(normalize_text(match.group(0))) > 2
        and normalize_text(match.group(0)) not in STOP_WORDS
        and normalize_text(match.group(0)) not in query_tokens
    )


def _pair_key(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def _temporal_proximity(left: datetime | None, right: datetime | None) -> float:
    if left is None or right is None:
        return 0.5
    hours = abs((left - right).total_seconds()) / 3600
    return math.exp(-math.log(2) * hours / (24 * 14))


def _weighted_jaccard(
    left: frozenset[str], right: frozenset[str], weights: Mapping[str, float]
) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    denominator = sum(weights.get(token, 1.0) for token in union)
    if denominator <= 0:
        return 0.0
    return sum(weights.get(token, 1.0) for token in left & right) / denominator


def build_cluster_candidate_plan(
    items: list[DeduplicationItem],
    *,
    query_tokens: Iterable[str] = (),
    duplicate_groups: Iterable[Iterable[int]] = (),
) -> ClusterCandidatePlan:
    """Build bounded plausible story pairs without comparing semantic vectors globally."""

    ordered = sorted(
        items,
        key=lambda item: (canonicalize_url(item.canonical_url), item.source, item.key),
    )
    by_key = {item.key: item for item in ordered}
    components_by_min, _component_by_key = _union_find_components(ordered, duplicate_groups)
    components: dict[int, tuple[int, ...]] = {}
    for members in components_by_min.values():
        components[_representative(members, by_key)] = members
    representative_keys = tuple(
        sorted(
            components,
            key=lambda key: (
                canonicalize_url(by_key[key].canonical_url),
                by_key[key].source,
                key,
            ),
        )
    )
    query_set = frozenset(normalize_text(token) for token in query_tokens if token)
    sequences: dict[int, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    document_frequency: Counter[str] = Counter()
    for key in representative_keys:
        item = by_key[key]
        title = _meaningful_sequence(item.title or "")
        body = _meaningful_sequence(item.text)
        sequences[key] = (title, body)
        document_frequency.update(set(title) | set(body))

    count = max(1, len(representative_keys))
    distinctive_frequency_limit = max(2, math.ceil(count * 0.35))
    # Story identifiers must remain rare in the session; broad/template vocabulary
    # may be distinctive enough for blocking but is not event identity evidence.
    identity_frequency_limit = max(4, math.ceil(count * 0.05))
    token_weights: dict[str, float] = {}
    for token, frequency in document_frequency.items():
        weight = math.log((count + 1) / (frequency + 0.5)) + 1
        if token in query_set:
            weight *= 0.05
        elif frequency / count > 0.35:
            weight *= 0.25
        token_weights[token] = weight

    features: dict[int, ClusterDocumentFeatures] = {}
    for key in representative_keys:
        item = by_key[key]
        title_sequence, body_sequence = sequences[key]
        title_tokens = frozenset(title_sequence)
        body_tokens = frozenset(body_sequence)
        all_tokens = title_tokens | body_tokens
        distinctive = frozenset(
            token
            for token in all_tokens
            if token not in query_set
            and document_frequency[token] <= distinctive_frequency_limit
            and token not in STOP_WORDS
        )
        identity = frozenset(
            token
            for token in distinctive
            if document_frequency[token] <= identity_frequency_limit
        )
        features[key] = ClusterDocumentFeatures(
            key=key,
            title_tokens=title_tokens,
            body_tokens=body_tokens,
            all_tokens=all_tokens,
            distinctive_tokens=distinctive,
            identity_tokens=identity,
            entity_tokens=_extract_entities(
                f"{item.title or ''} {item.text}", query_set
            ),
            title_phrases=frozenset(
                phrase
                for phrase in _phrases(title_sequence)
                if not set(phrase).issubset(query_set)
            ),
            language=detect_language(f"{item.title or ''} {item.text}"),
        )

    blocks: dict[tuple[str, object], list[int]] = defaultdict(list)
    for key, feature in features.items():
        for token in feature.identity_tokens:
            blocks[("token", token)].append(key)
        for entity in feature.entity_tokens & feature.identity_tokens:
            blocks[("entity", entity)].append(key)
        for phrase in feature.title_phrases:
            if set(phrase) & feature.identity_tokens:
                blocks[("phrase", phrase)].append(key)

    lexical_candidates: set[tuple[int, int]] = set()
    priorities: Counter[tuple[int, int]] = Counter()
    for block_keys in blocks.values():
        keys = sorted(set(block_keys))
        if len(keys) < 2 or len(keys) > MAX_BLOCK_SIZE:
            continue
        for left, right in combinations(keys, 2):
            pair = _pair_key(left, right)
            lexical_candidates.add(pair)
            priorities[pair] += 1

    temporal_candidates: set[tuple[int, int]] = set()
    dated = [key for key in representative_keys if by_key[key].published_at is not None]
    for left in dated:
        left_item = by_key[left]
        cross_language = sorted(
            (
                right
                for right in dated
                if right != left
                and features[left].language != features[right].language
                and features[left].language in {"ar", "en"}
                and features[right].language in {"ar", "en"}
            ),
            key=lambda right: (
                abs((left_item.published_at - by_key[right].published_at).total_seconds()),
                right,
            ),
        )[:MAX_TEMPORAL_NEIGHBORS]
        for right in cross_language:
            gap_seconds = abs(
                (left_item.published_at - by_key[right].published_at).total_seconds()
            )
            if gap_seconds <= 3 * 86400:
                temporal_candidates.add(_pair_key(left, right))

    all_candidates = lexical_candidates | temporal_candidates
    candidate_degree: Counter[int] = Counter()
    selected: list[tuple[int, int]] = []
    capped = 0
    for pair in sorted(
        all_candidates,
        key=lambda pair: (
            -priorities[pair],
            -_temporal_proximity(by_key[pair[0]].published_at, by_key[pair[1]].published_at),
            pair,
        ),
    ):
        left, right = pair
        if (
            candidate_degree[left] >= MAX_CANDIDATES_PER_ITEM
            or candidate_degree[right] >= MAX_CANDIDATES_PER_ITEM
        ):
            capped += 1
            continue
        selected.append(pair)
        candidate_degree[left] += 1
        candidate_degree[right] += 1

    return ClusterCandidatePlan(
        pairs=tuple(sorted(selected)),
        representative_keys=representative_keys,
        components=components,
        features=features,
        token_weights=token_weights,
        query_tokens=query_set,
        lexical_block_pairs=len(lexical_candidates),
        temporal_block_pairs=len(temporal_candidates),
        capped_pairs=capped,
    )


def cluster_pair_evidence(
    left: DeduplicationItem,
    right: DeduplicationItem,
    plan: ClusterCandidatePlan,
    semantic_similarity: float | None = None,
) -> ClusterPairEvidence:
    left_features, right_features = plan.features[left.key], plan.features[right.key]
    title_similarity = _weighted_jaccard(
        left_features.title_tokens, right_features.title_tokens, plan.token_weights
    )
    body_similarity = _weighted_jaccard(
        left_features.body_tokens, right_features.body_tokens, plan.token_weights
    )
    combined_similarity = _weighted_jaccard(
        left_features.all_tokens, right_features.all_tokens, plan.token_weights
    )
    shared_distinctive = tuple(
        sorted(
            left_features.distinctive_tokens & right_features.distinctive_tokens,
            key=lambda token: (-plan.token_weights.get(token, 1.0), token),
        )
    )
    shared_identifiers = tuple(
        sorted(
            left_features.identity_tokens & right_features.identity_tokens,
            key=lambda token: (-plan.token_weights.get(token, 1.0), token),
        )
    )
    shared_entities = tuple(sorted(left_features.entity_tokens & right_features.entity_tokens))
    shared_phrases = tuple(
        " ".join(phrase)
        for phrase in sorted(left_features.title_phrases & right_features.title_phrases)
    )
    temporal = _temporal_proximity(left.published_at, right.published_at)
    lexical_score = (
        0.45 * title_similarity + 0.35 * body_similarity + 0.20 * combined_similarity
    )
    strong_lexical = bool(shared_identifiers) and (
        combined_similarity >= 0.55
        or (
            len(shared_distinctive) >= 3
            and combined_similarity >= 0.20
            and max(title_similarity, body_similarity) >= 0.24
        )
        or (
            bool(shared_phrases)
            and len(shared_distinctive) >= 2
            and combined_similarity >= 0.18
            and body_similarity >= 0.12
        )
        or (
            bool(shared_phrases)
            and len(shared_distinctive) >= 3
            and title_similarity >= 0.30
            and temporal >= 0.50
        )
        or (
            title_similarity >= 0.52
            and len(shared_distinctive) >= 2
            and body_similarity >= 0.12
        )
    )
    cross_language = left_features.language != right_features.language
    semantic_threshold = SEMANTIC_STORY_THRESHOLD
    if temporal < 0.1 and combined_similarity < 0.70:
        semantic_threshold = LONG_GAP_SEMANTIC_THRESHOLD
    semantic_support = (
        semantic_similarity is not None
        and semantic_similarity >= semantic_threshold
        and (
            bool(shared_identifiers)
            or (cross_language and temporal >= 0.25)
        )
    )
    matched = strong_lexical or semantic_support
    reasons: list[str] = []
    if shared_distinctive:
        reasons.append("shared_distinctive_terms")
    if shared_identifiers:
        reasons.append("shared_story_identifiers")
    if shared_entities:
        reasons.append("entity_overlap")
    if shared_phrases:
        reasons.append("title_phrase_overlap")
    if semantic_support:
        reasons.append("semantic_similarity")
    if temporal >= 0.75:
        reasons.append("temporal_proximity")
    if strong_lexical:
        reasons.append("lexical_story_identity")
    score = max(
        lexical_score,
        semantic_similarity if semantic_support and semantic_similarity is not None else 0.0,
    )
    return ClusterPairEvidence(
        match=matched,
        score=round(score, 6),
        lexical_similarity=round(combined_similarity, 6),
        title_similarity=round(title_similarity, 6),
        body_similarity=round(body_similarity, 6),
        semantic_similarity=(
            round(semantic_similarity, 6) if semantic_similarity is not None else None
        ),
        temporal_proximity=round(temporal, 6),
        shared_distinctive_terms=shared_distinctive[:8],
        shared_story_identifiers=shared_identifiers[:8],
        shared_entities=shared_entities[:8],
        shared_title_phrases=shared_phrases[:6],
        reasons=tuple(reasons),
    )


def cluster_items(
    items: list[DeduplicationItem],
    *,
    query_tokens: Iterable[str] = (),
    duplicate_groups: Iterable[Iterable[int]] = (),
    semantic_similarities: Mapping[tuple[int, int], float] | None = None,
    candidate_plan: ClusterCandidatePlan | None = None,
) -> list[TopicCluster]:
    if not items:
        return []
    duplicate_group_values = tuple(tuple(group) for group in duplicate_groups)
    plan = candidate_plan or build_cluster_candidate_plan(
        items,
        query_tokens=query_tokens,
        duplicate_groups=duplicate_group_values,
    )
    by_key = {item.key: item for item in items}
    semantic = semantic_similarities or {}
    evidence: dict[tuple[int, int], ClusterPairEvidence] = {}
    for left_key, right_key in plan.pairs:
        evidence[(left_key, right_key)] = cluster_pair_evidence(
            by_key[left_key],
            by_key[right_key],
            plan,
            semantic.get((left_key, right_key)),
        )

    clusters: list[list[int]] = []
    admission: dict[int, ClusterPairEvidence] = {}
    for candidate in plan.representative_keys:
        destinations: list[tuple[float, int]] = []
        for index, cluster in enumerate(clusters):
            pair_evidence = [evidence.get(_pair_key(candidate, member)) for member in cluster]
            if pair_evidence and all(item is not None and item.match for item in pair_evidence):
                destinations.append(
                    (min(item.score for item in pair_evidence if item is not None), index)
                )
        if not destinations:
            clusters.append([candidate])
            continue
        score, destination = max(destinations, key=lambda value: (value[0], -value[1]))
        weakest = min(
            (
                evidence[_pair_key(candidate, member)]
                for member in clusters[destination]
            ),
            key=lambda item: (item.score, item.reasons),
        )
        admission[candidate] = weakest
        clusters[destination].append(candidate)

    output: list[TopicCluster] = []
    total_items = len(items)
    for representative_cluster in clusters:
        member_keys = tuple(
            sorted(
                key
                for representative in representative_cluster
                for key in plan.components[representative]
            )
        )
        cluster_representative = max(
            representative_cluster,
            key=lambda key: (
                len(plan.features[key].distinctive_tokens),
                bool(by_key[key].title),
                -key,
            ),
        )
        term_counts: Counter[str] = Counter()
        for key in representative_cluster:
            term_counts.update(plan.features[key].distinctive_tokens)
        dates = [by_key[key].published_at for key in member_keys if by_key[key].published_at]
        similarities: dict[int, float] = {}
        reasons: dict[int, tuple[str, ...]] = {}
        for representative in representative_cluster:
            component = plan.components[representative]
            component_evidence = admission.get(representative)
            for key in component:
                if key != representative:
                    similarities[key] = 1.0
                    reasons[key] = ("duplicate_component",)
                elif representative == representative_cluster[0]:
                    similarities[key] = 1.0
                    reasons[key] = ("cluster_seed",)
                else:
                    similarities[key] = component_evidence.score if component_evidence else 1.0
                    reasons[key] = component_evidence.reasons if component_evidence else ()
        average_similarity = sum(similarities.values()) / len(similarities)
        suspicious = (
            len(member_keys) >= 5
            and len(member_keys) / total_items >= 0.40
            and average_similarity < 0.85
        )
        output.append(
            TopicCluster(
                members=member_keys,
                representative_title=next(
                    (
                        by_key[key].title
                        for key in (cluster_representative, *member_keys)
                        if by_key[key].title
                    ),
                    by_key[member_keys[0]].text[:120],
                ),
                source_distribution=dict(
                    sorted(Counter(by_key[key].source for key in member_keys).items())
                ),
                earliest_at=min(dates) if dates else None,
                latest_at=max(dates) if dates else None,
                terms=tuple(
                    term
                    for term, _ in sorted(
                        term_counts.items(),
                        key=lambda value: (
                            -value[1],
                            -plan.token_weights.get(value[0], 1.0),
                            value[0],
                        ),
                    )[:8]
                ),
                member_similarities=similarities,
                member_reasons=reasons,
                suspicious=suspicious,
                suspicious_reason=(
                    "large_heterogeneous_cluster" if suspicious else None
                ),
            )
        )
    return output
