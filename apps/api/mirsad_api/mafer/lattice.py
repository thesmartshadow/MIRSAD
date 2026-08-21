from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from ..domains.query import ProcessedQuery, normalize_arabic
from .intent import IntentLabel, QueryIntentFingerprint


class QueryVariantType(StrEnum):
    ORIGINAL = "ORIGINAL"
    NORMALIZED = "NORMALIZED"
    EXACT = "EXACT"
    ARABIC_NORMALIZED = "ARABIC_NORMALIZED"
    HANDLE = "HANDLE"
    HASHTAG = "HASHTAG"
    IDENTIFIER = "IDENTIFIER"
    TRANSLITERATION = "TRANSLITERATION"
    ENTITY_ALIAS = "ENTITY_ALIAS"
    EVIDENCE_EXPANDED = "EVIDENCE_EXPANDED"


@dataclass(frozen=True, slots=True)
class QueryVariant:
    variant_id: str
    text: str
    parent_id: str | None
    transformation: QueryVariantType
    intent: tuple[str, ...]
    language: str
    confidence: float
    drift_risk: float
    round_created: int
    eligible_source_capabilities: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "text": self.text,
            "parent_id": self.parent_id,
            "transformation": self.transformation.value,
            "intent": list(self.intent),
            "language": self.language,
            "confidence": round(self.confidence, 3),
            "drift_risk": round(self.drift_risk, 3),
            "round_created": self.round_created,
            "eligible_source_capabilities": list(self.eligible_source_capabilities),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class QueryLattice:
    variants: tuple[QueryVariant, ...]
    max_variants: int

    @property
    def original(self) -> QueryVariant:
        return next(
            item for item in self.variants if item.transformation == QueryVariantType.ORIGINAL
        )

    def texts(self, *, max_round: int | None = None) -> tuple[str, ...]:
        values = (
            item.text
            for item in self.variants
            if max_round is None or item.round_created <= max_round
        )
        return tuple(dict.fromkeys(values))

    def confidences(self) -> dict[str, float]:
        output: dict[str, float] = {}
        for item in self.variants:
            output[item.text] = max(output.get(item.text, 0.0), item.confidence)
        return output

    def as_dict(self) -> dict[str, object]:
        return {
            "max_variants": self.max_variants,
            "variants": [item.as_dict() for item in self.variants],
        }


ARABIC_NAME_OVERRIDES = {
    "علي": "Ali",
    "فراس": "Firas",
    "محمد": "Mohammed",
    "محمود": "Mahmoud",
    "احمد": "Ahmed",
    "أحمد": "Ahmed",
    "رضا": "Reda",
    "حسن": "Hassan",
    "حسين": "Hussein",
    "عمر": "Omar",
    "بغداد": "Baghdad",
    "العراق": "Iraq",
}


def _variant_id(kind: QueryVariantType, text: str, parent: str | None) -> str:
    return hashlib.sha256(f"{kind.value}\0{text}\0{parent or ''}".encode()).hexdigest()[:20]


def _transliterate_name(value: str) -> str | None:
    tokens = value.split()
    if not 2 <= len(tokens) <= 5:
        return None
    converted = [ARABIC_NAME_OVERRIDES.get(token) for token in tokens]
    if any(item is None for item in converted):
        return None
    return " ".join(item for item in converted if item)


def build_query_lattice(
    processed: ProcessedQuery,
    fingerprint: QueryIntentFingerprint,
    *,
    max_variants: int = 6,
    aliases: Iterable[tuple[str, float]] = (),
    evidence_expansions: Iterable[tuple[str, float, float, str]] = (),
) -> QueryLattice:
    limit = max(1, min(max_variants, 12))
    variants: list[QueryVariant] = []

    def add(
        text: str,
        kind: QueryVariantType,
        *,
        parent: str | None,
        confidence: float,
        drift: float,
        round_created: int,
        capabilities: tuple[str, ...],
        reason: str,
        language: str | None = None,
    ) -> QueryVariant | None:
        clean = re.sub(r"\s+", " ", text.strip())
        if not clean or len(variants) >= limit:
            return None
        identifier = _variant_id(kind, clean, parent)
        if any(item.variant_id == identifier for item in variants):
            return None
        variant = QueryVariant(
            identifier,
            clean,
            parent,
            kind,
            tuple(label.value for label in fingerprint.labels),
            language or processed.language,
            max(0.0, min(confidence, 1.0)),
            max(0.0, min(drift, 1.0)),
            round_created,
            capabilities,
            reason,
        )
        variants.append(variant)
        return variant

    original = add(
        processed.original,
        QueryVariantType.ORIGINAL,
        parent=None,
        confidence=1.0,
        drift=0.0,
        round_created=1,
        capabilities=("keyword_search",),
        reason="verbatim user query; immutable lattice root",
    )
    assert original is not None
    normalized = add(
        processed.normalized,
        QueryVariantType.NORMALIZED,
        parent=original.variant_id,
        confidence=0.98,
        drift=0.02,
        round_created=1,
        capabilities=("keyword_search",),
        reason="deterministic Unicode/case/whitespace normalization",
    )
    parent = normalized.variant_id if normalized else original.variant_id

    if (
        fingerprint.has(IntentLabel.EXACT_PHRASE)
        or fingerprint.has(IntentLabel.PERSON_LIKE)
        or fingerprint.has(IntentLabel.ENTITY_LIKE)
    ):
        add(
            f'"{processed.original.strip(chr(34))}"',
            QueryVariantType.EXACT,
            parent=original.variant_id,
            confidence=0.97,
            drift=0.0,
            round_created=1,
            capabilities=("phrase_search",),
            reason="preserve phrase/name adjacency",
        )
    if fingerprint.has(IntentLabel.ARABIC) or fingerprint.has(IntentLabel.MIXED_LANGUAGE):
        arabic_normalized = normalize_arabic(processed.original)
        add(
            arabic_normalized,
            QueryVariantType.ARABIC_NORMALIZED,
            parent=original.variant_id,
            confidence=0.96,
            drift=0.03,
            round_created=1,
            capabilities=("keyword_search", "phrase_search"),
            reason="Arabic diacritic/tatweel and conservative letter normalization",
            language="ar" if not fingerprint.has(IntentLabel.MIXED_LANGUAGE) else "mixed",
        )
    if fingerprint.has(IntentLabel.HANDLE):
        add(
            processed.original,
            QueryVariantType.HANDLE,
            parent=original.variant_id,
            confidence=1.0,
            drift=0.0,
            round_created=1,
            capabilities=("author_search", "keyword_search"),
            reason="exact handle preservation",
        )
    if fingerprint.has(IntentLabel.HASHTAG):
        add(
            processed.original,
            QueryVariantType.HASHTAG,
            parent=original.variant_id,
            confidence=1.0,
            drift=0.0,
            round_created=1,
            capabilities=("hashtag_search",),
            reason="exact hashtag preservation",
        )
    if fingerprint.has(IntentLabel.IDENTIFIER):
        add(
            processed.original,
            QueryVariantType.IDENTIFIER,
            parent=original.variant_id,
            confidence=1.0,
            drift=0.0,
            round_created=1,
            capabilities=("identifier_search", "phrase_search", "keyword_search"),
            reason="distinctive identifier; semantic rewriting prohibited",
        )

    if fingerprint.has(IntentLabel.PERSON_LIKE) and fingerprint.has(IntentLabel.ARABIC):
        transliteration = _transliterate_name(processed.original)
        if transliteration:
            add(
                transliteration,
                QueryVariantType.TRANSLITERATION,
                parent=parent,
                confidence=0.78,
                drift=0.18,
                round_created=2,
                capabilities=("keyword_search", "author_search"),
                reason="bounded dictionary transliteration for a name-like Arabic query",
                language="en",
            )

    if not fingerprint.has(IntentLabel.IDENTIFIER):
        for alias, confidence in sorted(aliases, key=lambda value: (-value[1], value[0])):
            if confidence < 0.8:
                continue
            add(
                alias,
                QueryVariantType.ENTITY_ALIAS,
                parent=original.variant_id,
                confidence=confidence,
                drift=max(0.05, 1 - confidence),
                round_created=2,
                capabilities=("keyword_search", "author_search"),
                reason="high-confidence locally evidenced alias",
            )

    if not fingerprint.has(IntentLabel.IDENTIFIER):
        for text, confidence, drift, reason in evidence_expansions:
            if confidence < 0.7 or drift > 0.35:
                continue
            add(
                text,
                QueryVariantType.EVIDENCE_EXPANDED,
                parent=original.variant_id,
                confidence=confidence,
                drift=drift,
                round_created=3,
                capabilities=("keyword_search",),
                reason=reason,
            )
    return QueryLattice(tuple(variants), limit)


def append_evidence_variants(
    lattice: QueryLattice,
    expansions: Iterable[tuple[str, float, float, str]],
) -> QueryLattice:
    variants = list(lattice.variants)
    root = lattice.original
    for text, confidence, drift, reason in expansions:
        clean = re.sub(r"\s+", " ", text.strip())
        if not clean or len(variants) >= lattice.max_variants or confidence < 0.7 or drift > 0.35:
            continue
        identifier = _variant_id(QueryVariantType.EVIDENCE_EXPANDED, clean, root.variant_id)
        if any(item.variant_id == identifier for item in variants):
            continue
        variants.append(
            replace(
                root,
                variant_id=identifier,
                text=clean,
                parent_id=root.variant_id,
                transformation=QueryVariantType.EVIDENCE_EXPANDED,
                confidence=confidence,
                drift_risk=drift,
                round_created=3,
                reason=reason,
            )
        )
    return QueryLattice(tuple(variants), lattice.max_variants)
