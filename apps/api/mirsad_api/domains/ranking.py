from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import ceil

from .query import ProcessedQuery, normalize_text, token_sequence


@dataclass(frozen=True, slots=True)
class ScoreComponents:
    final_score: float
    relevance: float
    freshness: float
    engagement: float
    source_confidence: float
    cross_source_presence: float
    novelty: float
    spam_penalty: float
    matched_terms: tuple[str, ...]
    supporting_signal_factor: float
    pre_penalty_score: float
    weighted_components: dict[str, float]
    lexical_relevance: float
    semantic_relevance: float | None
    semantic_similarity: float | None
    semantic_weight: float
    secondary_quality_budget: float
    ranking_strategy: str
    relevance_features: dict[str, float]

    def explanation(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RelevanceFeatures:
    score: float
    matched_terms: tuple[str, ...]
    bm25: float
    exact_full_query: float
    body_exact_phrase: float
    title_exact_phrase: float
    title_token_coverage: float
    body_token_coverage: float
    query_token_coverage: float
    token_proximity: float
    intent_exact: float

    def explanation(self) -> dict[str, float]:
        return {
            key: round(float(value), 2)
            for key, value in asdict(self).items()
            if key not in {"score", "matched_terms"}
        }


def freshness_score(
    published_at: datetime | None,
    *,
    now: datetime | None = None,
    half_life_hours: float = 48.0,
) -> float:
    if published_at is None:
        return 25.0
    current = now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age_hours = max(0.0, (current - published_at).total_seconds() / 3600)
    decay_lambda = math.log(2) / max(0.01, half_life_hours)
    return round(100 * math.exp(-decay_lambda * age_hours), 2)


def relevance_score(
    query: ProcessedQuery,
    title: str | None,
    text: str,
    *,
    bm25_normalized: float = 50,
    canonical_url: str = "",
    author_handle: str | None = None,
    hashtags: tuple[str, ...] | list[str] | None = None,
) -> tuple[float, tuple[str, ...]]:
    features = relevance_features(
        query,
        title,
        text,
        bm25_normalized=bm25_normalized,
        canonical_url=canonical_url,
        author_handle=author_handle,
        hashtags=hashtags,
    )
    return features.score, features.matched_terms


def relevance_features(
    query: ProcessedQuery,
    title: str | None,
    text: str,
    *,
    bm25_normalized: float = 50,
    canonical_url: str = "",
    author_handle: str | None = None,
    hashtags: tuple[str, ...] | list[str] | None = None,
) -> RelevanceFeatures:
    normalized_title = normalize_text(title or "")
    normalized_text = normalize_text(text)
    normalized_url = normalize_text(canonical_url)
    normalized_handle = normalize_text((author_handle or "").removeprefix("@"))
    normalized_hashtags = tuple(normalize_text(tag.removeprefix("#")) for tag in hashtags or ())
    combined = " ".join(
        value
        for value in (
            normalized_title,
            normalized_text,
            normalized_handle,
            " ".join(normalized_hashtags),
        )
        if value
    )
    combined_sequence = token_sequence(combined)
    combined_tokens = set(combined_sequence)
    title_sequence = token_sequence(normalized_title)
    title_tokens = set(title_sequence)
    body_sequence = token_sequence(normalized_text)
    body_tokens = set(body_sequence)
    matched = tuple(token for token in query.tokens if token in combined_tokens)
    coverage = len(matched) / max(1, len(query.tokens))
    title_coverage = sum(token in title_tokens for token in query.tokens) / max(
        1, len(query.tokens)
    )
    body_coverage = sum(token in body_tokens for token in query.tokens) / max(1, len(query.tokens))
    exact_phrase = float(_contains_sequence(combined_sequence, query.sequence))
    body_phrase = float(_contains_sequence(body_sequence, query.sequence))
    title_phrase = float(_contains_sequence(title_sequence, query.sequence))
    proximity = _token_proximity(combined_sequence, query.tokens)
    intent_exact = 0.0
    if query.intent == "hashtag" and query.tokens:
        intent_exact = float(query.tokens[0] in normalized_hashtags)
    elif query.intent == "handle" and query.tokens:
        intent_exact = float(query.tokens[0] == normalized_handle)
    elif query.intent == "url":
        intent_exact = float(bool(query.normalized) and query.normalized in normalized_url)
    score = (
        35 * coverage
        + 15 * title_coverage
        + 15 * exact_phrase
        + 15 * title_phrase
        + 10 * proximity
        + 10 * (bm25_normalized / 100)
        + 10 * intent_exact
    )
    return RelevanceFeatures(
        score=round(min(100, score), 2),
        matched_terms=matched,
        bm25=round(max(0.0, min(100.0, bm25_normalized)), 2),
        exact_full_query=exact_phrase * 100,
        body_exact_phrase=body_phrase * 100,
        title_exact_phrase=title_phrase * 100,
        title_token_coverage=round(title_coverage * 100, 2),
        body_token_coverage=round(body_coverage * 100, 2),
        query_token_coverage=round(coverage * 100, 2),
        token_proximity=round(proximity * 100, 2),
        intent_exact=intent_exact * 100,
    )


def _contains_sequence(content: tuple[str, ...], query: tuple[str, ...]) -> bool:
    if not content or not query or len(query) > len(content):
        return False
    width = len(query)
    return any(content[index : index + width] == query for index in range(len(content) - width + 1))


def _token_proximity(content: tuple[str, ...], query: tuple[str, ...]) -> float:
    required = set(query)
    if not content or not required or not required.issubset(content):
        return 0.0
    counts: dict[str, int] = {}
    left = 0
    best = len(content) + 1
    for right, token in enumerate(content):
        if token in required:
            counts[token] = counts.get(token, 0) + 1
        while len(counts) == len(required):
            best = min(best, right - left + 1)
            left_token = content[left]
            if left_token in counts:
                counts[left_token] -= 1
                if counts[left_token] == 0:
                    del counts[left_token]
            left += 1
    return min(1.0, len(required) / best) if best <= len(content) else 0.0


def is_candidate_match(
    query: ProcessedQuery,
    title: str | None,
    text: str,
    *,
    canonical_url: str = "",
    author_handle: str | None = None,
    hashtags: tuple[str, ...] | list[str] | None = None,
) -> bool:
    content = token_sequence(
        " ".join(
            (
                title or "",
                text,
                author_handle or "",
                " ".join(hashtags or ()),
            )
        )
    )
    if query.exact_phrase:
        return _contains_sequence(content, query.sequence)
    if query.intent == "url":
        return bool(query.normalized) and query.normalized in normalize_text(canonical_url)
    if query.intent == "handle" and query.tokens:
        return query.tokens[0] == normalize_text((author_handle or "").removeprefix("@"))
    if query.intent == "hashtag" and query.tokens:
        normalized_tags = {normalize_text(tag.removeprefix("#")) for tag in hashtags or ()}
        literal_hashtags = {
            normalize_text(token.removeprefix("#"))
            for token in (title or "").split() + text.split()
            if token.startswith("#")
        }
        return query.tokens[0] in normalized_tags or query.tokens[0] in literal_hashtags
    matched = len(set(query.tokens) & set(content))
    if len(query.tokens) <= 1:
        required = 1
    elif len(query.tokens) == 2:
        required = 2
    else:
        required = ceil(len(query.tokens) * 0.6)
    return bool(query.tokens) and matched >= required


def spam_penalty(title: str | None, text: str, canonical_url: str) -> float:
    combined = f"{title or ''} {text}"
    penalty = 0.0
    if len(text.strip()) < 40:
        penalty += 5
    if combined.count("!") >= 5:
        penalty += 6
    if sum(character.isupper() for character in combined) / max(1, len(combined)) > 0.45:
        penalty += 5
    if canonical_url.count("utm_") > 1:
        penalty += 2
    return min(20.0, penalty)


def calculate_score(
    *,
    query: ProcessedQuery,
    title: str | None,
    text: str,
    canonical_url: str,
    published_at: datetime | None,
    engagement: float,
    source_confidence: float,
    cross_source_presence: float = 0,
    novelty: float = 100,
    bm25_normalized: float = 50,
    author_handle: str | None = None,
    hashtags: tuple[str, ...] | list[str] | None = None,
    semantic_relevance: float | None = None,
    semantic_similarity: float | None = None,
    semantic_weight: float = 0.75,
    semantic_quality_budget: float = 0.01,
    weights: dict[str, float],
    half_life_hours: float = 48,
    now: datetime | None = None,
) -> ScoreComponents:
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Ranking weights must total 1.0")
    features = relevance_features(
        query,
        title,
        text,
        bm25_normalized=bm25_normalized,
        canonical_url=canonical_url,
        author_handle=author_handle,
        hashtags=hashtags,
    )
    lexical_relevance = features.score
    semantic = (
        round(max(0.0, min(100.0, semantic_relevance)), 2)
        if semantic_relevance is not None
        else None
    )
    semantic_weight = max(0.0, min(1.0, semantic_weight)) if semantic is not None else 0.0
    relevance = (
        round(
            (1 - semantic_weight) * lexical_relevance + semantic_weight * semantic,
            2,
        )
        if semantic is not None
        else lexical_relevance
    )
    freshness = freshness_score(published_at, now=now, half_life_hours=half_life_hours)
    penalty = spam_penalty(title, text, canonical_url)
    values = {
        "relevance": relevance,
        "freshness": freshness,
        "engagement": engagement,
        "source_confidence": source_confidence,
        "cross_source_presence": cross_source_presence,
        "novelty": novelty,
    }
    supporting_factor = round((relevance / 100.0) ** 2, 4)
    if semantic is None:
        weighted = {key: round(weights[key] * value, 4) for key, value in values.items()}
        # Supporting signals break ties among relevant candidates without rescuing weak matches.
        pre_penalty = weighted["relevance"] + supporting_factor * sum(
            value for key, value in weighted.items() if key != "relevance"
        )
        ranking_strategy = "lexical_explainable"
        quality_budget = 1 - weights["relevance"]
    else:
        quality_budget = max(0.0, min(0.05, semantic_quality_budget))
        secondary_weight_total = sum(
            weight for key, weight in weights.items() if key != "relevance"
        )
        secondary_quality = sum(
            weights[key] * values[key] for key in values if key != "relevance"
        ) / max(1e-9, secondary_weight_total)
        weighted = {
            "relevance": round((1 - quality_budget) * relevance, 4),
            **{
                key: round(
                    quality_budget
                    * supporting_factor
                    * weights[key]
                    / max(1e-9, secondary_weight_total)
                    * values[key],
                    4,
                )
                for key in values
                if key != "relevance"
            },
        }
        pre_penalty = (1 - quality_budget) * relevance + (
            quality_budget * supporting_factor * secondary_quality
        )
        ranking_strategy = "lexical_candidate_semantic_rerank"
    final = pre_penalty - penalty
    return ScoreComponents(
        final_score=round(max(0, min(100, final)), 2),
        relevance=relevance,
        freshness=freshness,
        engagement=round(max(0, min(100, engagement)), 2),
        source_confidence=round(max(0, min(100, source_confidence)), 2),
        cross_source_presence=round(max(0, min(100, cross_source_presence)), 2),
        novelty=round(max(0, min(100, novelty)), 2),
        spam_penalty=penalty,
        matched_terms=features.matched_terms,
        supporting_signal_factor=supporting_factor,
        pre_penalty_score=round(pre_penalty, 2),
        weighted_components=weighted,
        lexical_relevance=lexical_relevance,
        semantic_relevance=semantic,
        semantic_similarity=(
            round(max(-1.0, min(1.0, semantic_similarity)), 6)
            if semantic_similarity is not None
            else None
        ),
        semantic_weight=round(semantic_weight, 2),
        secondary_quality_budget=round(quality_budget, 4),
        ranking_strategy=ranking_strategy,
        relevance_features=features.explanation(),
    )
