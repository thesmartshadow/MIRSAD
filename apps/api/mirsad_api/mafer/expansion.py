from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ..domains.query import normalize_text, tokenize
from .intent import IntentLabel, QueryIntentFingerprint

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "news",
    "عن",
    "من",
    "في",
    "على",
    "الى",
    "إلى",
    "هذا",
    "هذه",
    "التي",
    "الذي",
}
RAW_TOKEN_PATTERN = re.compile(r"[#@]?[\w.-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ExpansionCandidate:
    term: str
    supporting_results: tuple[str, ...]
    support_count: int
    confidence: float
    drift_risk: float
    accepted: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "term": self.term,
            "supporting_results": list(self.supporting_results),
            "support_count": self.support_count,
            "confidence": round(self.confidence, 3),
            "drift_risk": round(self.drift_risk, 3),
            "accepted": self.accepted,
            "reason": self.reason,
        }


def propose_evidence_expansions(
    fingerprint: QueryIntentFingerprint,
    evidence: Iterable[tuple[str, str]],
    *,
    max_terms: int = 2,
) -> tuple[ExpansionCandidate, ...]:
    if fingerprint.has(IntentLabel.IDENTIFIER) or fingerprint.has(IntentLabel.AMBIGUOUS):
        return ()
    original_tokens = set(tokenize(fingerprint.normalized))
    supporting: dict[str, set[str]] = defaultdict(set)
    display: dict[str, str] = {}
    for result_id, text in evidence:
        for raw_token in RAW_TOKEN_PATTERN.findall(text):
            normalized = normalize_text(raw_token)
            if (
                len(normalized) < 4
                or normalized in original_tokens
                or normalized in STOPWORDS
                or normalized.isdigit()
            ):
                continue
            supporting[normalized].add(result_id)
            display.setdefault(normalized, raw_token)
    counts = Counter({term: len(results) for term, results in supporting.items()})
    output: list[ExpansionCandidate] = []
    for term, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if len(output) >= max(1, min(max_terms, 3)):
            break
        independent_sources = {result_id.partition(":")[0] for result_id in supporting[term]}
        raw_term = display[term]
        distinctive_form = (
            raw_term.startswith(("#", "@"))
            or any(character.isdigit() for character in raw_term)
            or "-" in raw_term
            or "." in raw_term
            or any("\u0600" <= character <= "\u06ff" for character in raw_term)
            or (len(raw_term) >= 6 and any(character.isupper() for character in raw_term))
        )
        confidence = min(0.92, 0.52 + 0.1 * count + 0.06 * len(independent_sources))
        drift = 0.22 if len(independent_sources) >= 3 else 0.3
        accepted = (
            distinctive_form
            and count >= 3
            and len(independent_sources) >= 2
            and confidence >= 0.78
            and drift <= 0.35
        )
        phrase = f"{fingerprint.original} {display[term]}"
        output.append(
            ExpansionCandidate(
                phrase,
                tuple(sorted(supporting[term])),
                count,
                confidence,
                drift,
                accepted,
                "retains original query and adds a term supported by multiple independent sources"
                if accepted
                else (
                    "candidate is not a distinctive entity, handle, hashtag, or identifier"
                    if not distinctive_form
                    else "insufficient cross-source support or excessive drift risk"
                ),
            )
        )
    return tuple(output)
