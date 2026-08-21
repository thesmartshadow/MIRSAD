from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ..domains.query import (
    ARABIC_CHARACTERS,
    LATIN_CHARACTERS,
    ProcessedQuery,
    token_sequence,
)

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
DOMAIN_PATTERN = re.compile(
    r"(?<![@\w])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?:/[^\s]*)?",
    re.IGNORECASE,
)
QUOTED_PATTERN = re.compile(r'["“”]([^"“”]{1,300})["“”]')
HANDLE_PATTERN = re.compile(r"(?<!\w)@[A-Za-z0-9_.-]{2,64}\b")
HASHTAG_PATTERN = re.compile(r"(?<!\w)#[\w\u0600-\u06ff]{1,80}\b", re.UNICODE)
CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
GHSA_PATTERN = re.compile(
    r"\bGHSA-[23456789cfghjmpqrvwx]{4}(?:-[23456789cfghjmpqrvwx]{4}){2}\b",
    re.IGNORECASE,
)
CWE_PATTERN = re.compile(r"\bCWE-\d{1,5}\b", re.IGNORECASE)
COMMIT_PATTERN = re.compile(r"(?<![A-Fa-f0-9])[A-Fa-f0-9]{7,40}(?![A-Fa-f0-9])")
REPOSITORY_PATTERN = re.compile(r"\b[A-Za-z0-9_.-]{1,80}/[A-Za-z0-9_.-]{1,100}\b")
PACKAGE_PATTERN = re.compile(
    r"(?:\b(?:npm|pypi|crate|package):[A-Za-z0-9_.@/-]{2,120}\b|(?<!\w)@[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


class IntentLabel(StrEnum):
    HANDLE = "HANDLE"
    HASHTAG = "HASHTAG"
    PERSON_LIKE = "PERSON_LIKE"
    ENTITY_LIKE = "ENTITY_LIKE"
    TOPIC = "TOPIC"
    EVENT_LIKE = "EVENT_LIKE"
    EXACT_PHRASE = "EXACT_PHRASE"
    URL = "URL"
    DOMAIN = "DOMAIN"
    IDENTIFIER = "IDENTIFIER"
    RECENT_INTENT = "RECENT_INTENT"
    HISTORICAL_INTENT = "HISTORICAL_INTENT"
    AMBIGUOUS = "AMBIGUOUS"
    ARABIC = "ARABIC"
    ENGLISH = "ENGLISH"
    MIXED_LANGUAGE = "MIXED_LANGUAGE"


class TemporalIntent(StrEnum):
    TIME_CRITICAL = "TIME_CRITICAL"
    RECENT_PREFERRED = "RECENT_PREFERRED"
    TIME_NEUTRAL = "TIME_NEUTRAL"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True, slots=True)
class IntentEvidence:
    label: IntentLabel
    confidence: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "confidence": round(self.confidence, 3),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class QueryIntentFingerprint:
    original: str
    normalized: str
    labels: tuple[IntentLabel, ...]
    evidence: tuple[IntentEvidence, ...]
    temporal_intent: TemporalIntent
    token_count: int
    quoted_segments: tuple[str, ...]
    contains_hashtag: bool
    contains_handle: bool
    contains_url: bool
    contains_domain: bool
    script_distribution: dict[str, float]
    token_rarity: dict[str, float]
    query_length: int
    temporal_terms: tuple[str, ...]
    identifier_patterns: tuple[str, ...]
    ambiguity_indicators: tuple[str, ...]

    def has(self, label: IntentLabel) -> bool:
        return label in self.labels

    def confidence_for(self, label: IntentLabel) -> float:
        return next((item.confidence for item in self.evidence if item.label == label), 0.0)

    def as_dict(self) -> dict[str, object]:
        return {
            "labels": [label.value for label in self.labels],
            "evidence": [item.as_dict() for item in self.evidence],
            "temporal_intent": self.temporal_intent.value,
            "token_count": self.token_count,
            "quoted_segments": list(self.quoted_segments),
            "contains_hashtag": self.contains_hashtag,
            "contains_handle": self.contains_handle,
            "contains_url": self.contains_url,
            "contains_domain": self.contains_domain,
            "script_distribution": self.script_distribution,
            "token_rarity": self.token_rarity,
            "query_length": self.query_length,
            "temporal_terms": list(self.temporal_terms),
            "identifier_patterns": list(self.identifier_patterns),
            "ambiguity_indicators": list(self.ambiguity_indicators),
        }


RECENT_TERMS = {
    "latest",
    "breaking",
    "today",
    "now",
    "recent",
    "new",
    "current",
    "احدث",
    "عاجل",
    "اليوم",
    "الان",
    "حديث",
}
HISTORICAL_TERMS = {
    "history",
    "historical",
    "archive",
    "archived",
    "timeline",
    "تاريخ",
    "تاريخي",
    "ارشيف",
    "أرشيف",
}
EVENT_TERMS = {
    "launch",
    "launched",
    "release",
    "released",
    "announced",
    "election",
    "incident",
    "attack",
    "conference",
    "اطلاق",
    "إطلاق",
    "اعلان",
    "إعلان",
    "انتخابات",
    "حادث",
    "مؤتمر",
}
ORG_TERMS = {
    "ministry",
    "university",
    "company",
    "foundation",
    "agency",
    "organization",
    "وزارة",
    "وزاره",
    "جامعة",
    "شركة",
    "هيئة",
    "مؤسسة",
    "منظمة",
}
TOPIC_MARKERS = {
    "ai",
    "artificial",
    "intelligence",
    "security",
    "technology",
    "الذكاء",
    "الاصطناعي",
    "التقنيه",
    "التقنية",
    "التكنولوجيا",
}
COMMON_AMBIGUOUS = {
    "apple",
    "amazon",
    "jordan",
    "java",
    "mercury",
    "ai",
    "technology",
    "news",
    "العراق",
    "بغداد",
    "تقنية",
}


class QueryIntentAnalyzer:
    """Explainable query-shape analysis; labels are heuristic, not identity claims."""

    def analyze(
        self,
        processed: ProcessedQuery,
        *,
        token_document_frequency: Mapping[str, int] | None = None,
        document_count: int = 0,
        explicit_time_range: str = "all",
    ) -> QueryIntentFingerprint:
        original = unicodedata.normalize("NFKC", processed.original).strip()
        normalized = processed.normalized
        sequence = token_sequence(normalized)
        lowered = set(sequence)
        quoted = tuple(value.strip() for value in QUOTED_PATTERN.findall(original) if value.strip())
        handles = HANDLE_PATTERN.findall(original)
        hashtags = HASHTAG_PATTERN.findall(original)
        urls = URL_PATTERN.findall(original)
        domains = DOMAIN_PATTERN.findall(original)
        identifiers: list[str] = []
        for name, pattern in (
            ("CVE", CVE_PATTERN),
            ("GHSA", GHSA_PATTERN),
            ("CWE", CWE_PATTERN),
            ("COMMIT", COMMIT_PATTERN),
            ("PACKAGE", PACKAGE_PATTERN),
            ("REPOSITORY", REPOSITORY_PATTERN),
        ):
            if pattern.search(original):
                identifiers.append(name)
        if urls:
            identifiers.append("URL")
        elif domains:
            identifiers.append("DOMAIN")
        if handles:
            identifiers.append("HANDLE")

        script_distribution = self._script_distribution(original)
        rarity = self._token_rarity(
            processed.tokens, token_document_frequency or {}, document_count
        )
        ambiguity: list[str] = []
        if len(sequence) == 1:
            ambiguity.append("single_token")
        if normalized in COMMON_AMBIGUOUS:
            ambiguity.append("known_polysemous_or_broad_term")
        if sequence and all(rarity.get(token, 0.5) < 0.25 for token in set(sequence)):
            ambiguity.append("only_common_terms")

        evidence: list[IntentEvidence] = []

        def add(label: IntentLabel, confidence: float, *reasons: str) -> None:
            evidence.append(IntentEvidence(label, max(0.0, min(confidence, 1.0)), tuple(reasons)))

        if handles:
            add(IntentLabel.HANDLE, 0.99, "query contains an @handle pattern")
        if hashtags:
            add(IntentLabel.HASHTAG, 0.99, "query contains a hashtag pattern")
        if urls:
            add(IntentLabel.URL, 1.0, "query contains an HTTP(S) URL")
        if domains:
            add(IntentLabel.DOMAIN, 0.98, "query contains a domain pattern")
        if identifiers:
            add(
                IntentLabel.IDENTIFIER,
                0.99 if any(item in {"CVE", "GHSA", "CWE"} for item in identifiers) else 0.9,
                f"distinctive identifier pattern: {', '.join(dict.fromkeys(identifiers))}",
            )
        if quoted or processed.exact_phrase:
            add(IntentLabel.EXACT_PHRASE, 0.98, "quoted text or exact-phrase mode")

        has_arabic = bool(ARABIC_CHARACTERS.search(original))
        has_latin = bool(LATIN_CHARACTERS.search(original))
        if has_arabic and has_latin:
            add(IntentLabel.MIXED_LANGUAGE, 0.99, "Arabic and Latin scripts are both present")
        elif has_arabic:
            add(IntentLabel.ARABIC, 0.99, "Arabic-script letters dominate the query")
        elif has_latin:
            add(IntentLabel.ENGLISH, 0.95, "Latin-script letters dominate the query")

        organization_term = next((term for term in lowered if term in ORG_TERMS), None)
        literal_words = [
            token.strip("'\".,:;!?()[]{}")
            for token in original.split()
            if token.strip("'\".,:;!?()[]{}")
        ]
        title_like = (
            1 < len(sequence) <= 6
            and len(literal_words) == len(sequence)
            and all(token[:1].isupper() for token in literal_words)
        )
        arabic_name_like = (
            has_arabic
            and not has_latin
            and 2 <= len(sequence) <= 5
            and not organization_term
            and not (lowered & TOPIC_MARKERS)
            and not (lowered & (RECENT_TERMS | HISTORICAL_TERMS | EVENT_TERMS))
        )
        if organization_term or title_like or (has_arabic and has_latin and len(sequence) <= 6):
            add(
                IntentLabel.ENTITY_LIKE,
                0.82 if organization_term or title_like else 0.68,
                "organization marker, capitalization, or mixed-script name-like phrase",
            )
        if (
            arabic_name_like or (title_like and len(sequence) <= 4 and not organization_term)
        ) and not (identifiers or handles or urls or hashtags or (has_arabic and has_latin)):
            add(
                IntentLabel.PERSON_LIKE,
                0.72 if arabic_name_like else 0.64,
                "short name-like token sequence; heuristic only",
            )
        if lowered & EVENT_TERMS or (
            YEAR_PATTERN.search(original) and len(sequence) > 1 and not identifiers
        ):
            add(IntentLabel.EVENT_LIKE, 0.78, "event term or dated phrase")
        if not identifiers and not urls and not handles:
            add(
                IntentLabel.TOPIC,
                0.8 if len(sequence) > 1 else 0.55,
                "query describes searchable terms",
            )
        if ambiguity:
            add(IntentLabel.AMBIGUOUS, 0.86 if len(ambiguity) > 1 else 0.65, *ambiguity)

        temporal_terms = tuple(
            token for token in sequence if token in RECENT_TERMS or token in HISTORICAL_TERMS
        )
        temporal = self._temporal_intent(
            lowered,
            original,
            explicit_time_range=explicit_time_range,
            identifier_present=bool(identifiers),
        )
        if temporal in {TemporalIntent.TIME_CRITICAL, TemporalIntent.RECENT_PREFERRED}:
            add(
                IntentLabel.RECENT_INTENT,
                0.95 if temporal == TemporalIntent.TIME_CRITICAL else 0.75,
                temporal.value,
            )
        elif temporal == TemporalIntent.HISTORICAL:
            add(IntentLabel.HISTORICAL_INTENT, 0.92, "historical term, year, or all-time intent")

        deduped: dict[IntentLabel, IntentEvidence] = {}
        for item in evidence:
            current = deduped.get(item.label)
            if current is None or item.confidence > current.confidence:
                deduped[item.label] = item
        ordered = tuple(
            sorted(
                deduped.values(),
                key=lambda item: (-item.confidence, item.label.value),
            )
        )
        return QueryIntentFingerprint(
            original=original,
            normalized=normalized,
            labels=tuple(item.label for item in ordered),
            evidence=ordered,
            temporal_intent=temporal,
            token_count=len(sequence),
            quoted_segments=quoted,
            contains_hashtag=bool(hashtags),
            contains_handle=bool(handles),
            contains_url=bool(urls),
            contains_domain=bool(domains),
            script_distribution=script_distribution,
            token_rarity=rarity,
            query_length=len(original),
            temporal_terms=temporal_terms,
            identifier_patterns=tuple(dict.fromkeys(identifiers)),
            ambiguity_indicators=tuple(ambiguity),
        )

    @staticmethod
    def _script_distribution(value: str) -> dict[str, float]:
        letters = [character for character in value if character.isalpha()]
        if not letters:
            return {"arabic": 0.0, "latin": 0.0, "other": 0.0}
        arabic = sum(bool(ARABIC_CHARACTERS.fullmatch(character)) for character in letters)
        latin = sum(bool(LATIN_CHARACTERS.fullmatch(character)) for character in letters)
        total = len(letters)
        return {
            "arabic": round(arabic / total, 3),
            "latin": round(latin / total, 3),
            "other": round((total - arabic - latin) / total, 3),
        }

    @staticmethod
    def _token_rarity(
        tokens: tuple[str, ...], frequencies: Mapping[str, int], document_count: int
    ) -> dict[str, float]:
        if not tokens:
            return {}
        if document_count <= 0:
            return {token: 0.5 for token in tokens}
        return {
            token: round(
                min(
                    1.0,
                    math.log((document_count + 1) / (frequencies.get(token, 0) + 1))
                    / math.log(document_count + 1),
                ),
                3,
            )
            for token in tokens
        }

    @staticmethod
    def _temporal_intent(
        tokens: set[str],
        original: str,
        *,
        explicit_time_range: str,
        identifier_present: bool,
    ) -> TemporalIntent:
        if explicit_time_range in {"24h", "7d"}:
            return (
                TemporalIntent.TIME_CRITICAL
                if explicit_time_range == "24h"
                else TemporalIntent.RECENT_PREFERRED
            )
        if tokens & HISTORICAL_TERMS or (YEAR_PATTERN.search(original) and not identifier_present):
            return TemporalIntent.HISTORICAL
        if tokens & {"latest", "breaking", "today", "now", "عاجل", "اليوم", "الان"}:
            return TemporalIntent.TIME_CRITICAL
        if tokens & RECENT_TERMS or explicit_time_range == "30d":
            return TemporalIntent.RECENT_PREFERRED
        return TemporalIntent.TIME_NEUTRAL
