from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
ARABIC_CHARACTERS = re.compile(r"[\u0600-\u06ff]")
TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
LATIN_CHARACTERS = re.compile(r"[A-Za-z]")
FORMAT_CONTROLS = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
URL_QUERY = re.compile(r"^https?://|^[\w.-]+\.[A-Za-z]{2,}(?:/|$)", re.IGNORECASE)
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
QueryIntent = Literal[
    "keywords",
    "exact_phrase",
    "hashtag",
    "handle",
    "url",
    "mixed_language",
    "organization_phrase",
]
QueryType = Literal[
    "EXACT_PHRASE",
    "HASHTAG",
    "HANDLE",
    "URL",
    "RARE_ENTITY",
    "MULTI_TERM_TOPIC",
    "SHORT_AMBIGUOUS",
    "MIXED_LANGUAGE",
]


@dataclass(frozen=True, slots=True)
class ProcessedQuery:
    original: str
    normalized: str
    language: str
    tokens: tuple[str, ...]
    sequence: tuple[str, ...]
    variants: tuple[str, ...]
    variant_reasons: tuple[tuple[str, str], ...]
    exact_phrase: bool
    intent: QueryIntent


def normalize_arabic(value: str) -> str:
    value = ARABIC_DIACRITICS.sub("", value)
    return value.translate(
        str.maketrans(
            {
                "أ": "ا",
                "إ": "ا",
                "آ": "ا",
                "ٱ": "ا",
                "ى": "ي",
                "ؤ": "و",
                "ئ": "ي",
                "ة": "ه",
                "ـ": "",
            }
        )
    )


def normalize_text(value: str) -> str:
    value = FORMAT_CONTROLS.sub("", unicodedata.normalize("NFKC", value)).strip()
    value = value.translate(ARABIC_DIGITS)
    value = normalize_arabic(value)
    value = value.casefold()
    return re.sub(r"\s+", " ", value)


def detect_language(value: str) -> str:
    letters = [character for character in value if character.isalpha()]
    if not letters:
        return "und"
    arabic = len(ARABIC_CHARACTERS.findall(value))
    return "ar" if arabic / len(letters) >= 0.3 else "en"


def resolve_content_language(reported: str | None, content: str) -> str:
    """Canonicalize common upstream labels, detecting only when a label is unusable."""

    value = (reported or "").strip().casefold().replace("_", "-")
    aliases = {
        "ar": "ar",
        "ara": "ar",
        "arabic": "ar",
        "العربية": "ar",
        "en": "en",
        "eng": "en",
        "english": "en",
    }
    if value in aliases:
        return aliases[value]
    primary = value.split("-", 1)[0]
    if primary in {"ar", "en"}:
        return primary
    if len(primary) in {2, 3} and primary not in {"und", "unk"}:
        return primary
    return detect_language(content)


def token_sequence(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_PATTERN.findall(normalize_text(value)))


def tokenize(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token_sequence(value)))


def process_query(value: str, *, exact_phrase: bool = False) -> ProcessedQuery:
    original = unicodedata.normalize("NFKC", value).strip()
    quoted = len(original) >= 2 and original.startswith('"') and original.endswith('"')
    query_value = original[1:-1].strip() if quoted else original
    exact = exact_phrase or quoted
    normalized = normalize_text(query_value)
    sequence = token_sequence(normalized)
    tokens = tuple(dict.fromkeys(sequence))
    variants: list[tuple[str, str]] = [(normalized, "normalized_query")]
    if detect_language(normalized) == "ar":
        without_article = " ".join(
            token[2:] if token.startswith("ال") and len(token) > 4 else token for token in tokens
        )
        if without_article and without_article != normalized:
            variants.append((without_article, "arabic_definite_article_variant"))
    if original.startswith("#") and tokens:
        intent: QueryIntent = "hashtag"
    elif original.startswith("@") and tokens:
        intent = "handle"
    elif URL_QUERY.search(query_value):
        intent = "url"
    elif ARABIC_CHARACTERS.search(query_value) and LATIN_CHARACTERS.search(query_value):
        intent = "mixed_language"
    elif exact:
        intent = "exact_phrase"
    elif 1 < len(tokens) <= 5 and any(character.isupper() for character in original):
        intent = "organization_phrase"
    else:
        intent = "keywords"
    unique_variants = tuple(dict.fromkeys(variant for variant, _reason in variants))
    unique_details = tuple(dict.fromkeys(variants))
    return ProcessedQuery(
        original=original,
        normalized=normalized,
        language=detect_language(normalized),
        tokens=tokens,
        sequence=sequence,
        variants=unique_variants,
        variant_reasons=unique_details,
        exact_phrase=exact,
        intent=intent,
    )


def fts_query(processed: ProcessedQuery) -> str:
    source = processed.sequence if processed.exact_phrase else processed.tokens
    safe_tokens = [token.replace('"', '""') for token in source]
    if not safe_tokens:
        return '""'
    if processed.exact_phrase:
        return f'"{" ".join(safe_tokens)}"'
    return " OR ".join(f'"{token}"' for token in safe_tokens)


def classify_query(processed: ProcessedQuery) -> QueryType:
    """Classify query shape without broadening or rewriting the user's terms."""

    if processed.intent == "hashtag":
        return "HASHTAG"
    if processed.intent == "handle":
        return "HANDLE"
    if processed.intent == "url":
        return "URL"
    if processed.exact_phrase:
        return "EXACT_PHRASE"
    if processed.intent == "mixed_language":
        return "MIXED_LANGUAGE"
    if len(processed.tokens) == 1:
        return "SHORT_AMBIGUOUS"
    if processed.intent == "organization_phrase":
        return "RARE_ENTITY"
    return "MULTI_TERM_TOPIC"
