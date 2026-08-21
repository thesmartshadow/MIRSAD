# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean, median, pstdev
from typing import Any

from .domains.clustering import cluster_items
from .domains.deduplication import DeduplicationItem, find_duplicate_groups
from .domains.query import normalize_text, process_query, tokenize
from .domains.ranking import (
    calculate_score,
    freshness_score,
    is_candidate_match,
    spam_penalty,
)

EVALUATION_NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)
DEFAULT_WEIGHTS = {
    "relevance": 0.35,
    "freshness": 0.20,
    "engagement": 0.15,
    "source_confidence": 0.10,
    "cross_source_presence": 0.10,
    "novelty": 0.10,
}


@dataclass(frozen=True, slots=True)
class EvaluationDocument:
    id: str
    source: str
    title: str
    text: str
    age_hours: int
    engagement: float
    url: str
    author_handle: str | None = None
    hashtags: tuple[str, ...] = ()


DOCUMENTS = (
    EvaluationDocument(
        "e01",
        "rss",
        "Climate policy annual report",
        "Evidence on climate policy implementation.",
        4,
        8,
        "https://news.example/climate-report",
    ),
    EvaluationDocument(
        "e02",
        "gdelt",
        "Annual report: climate policy",
        "Evidence on climate policy implementation.",
        5,
        14,
        "https://news.example/climate-report?utm_source=x",
    ),
    EvaluationDocument(
        "e03",
        "hacker_news",
        "Climate strategy game reaches a million players",
        "Entertainment release with high engagement.",
        1,
        98,
        "https://games.example/climate",
    ),
    EvaluationDocument(
        "e04",
        "github",
        "Acme Organization public roadmap",
        "Official Acme Organization repository and roadmap.",
        12,
        34,
        "https://github.com/acme/roadmap",
    ),
    EvaluationDocument(
        "e05",
        "rss",
        "Acme detergent sale",
        "Retail prices for an unrelated Acme product.",
        2,
        80,
        "https://shop.example/acme",
    ),
    EvaluationDocument(
        "e06",
        "github",
        "Open data portal",
        "Municipal open data portal source repository.",
        30,
        45,
        "https://github.com/city/open-data",
    ),
    EvaluationDocument(
        "e07",
        "rss",
        "Portal publishes open data",
        "The city released datasets through its open data portal.",
        10,
        12,
        "https://city.example/open-data",
    ),
    EvaluationDocument(
        "e08",
        "hacker_news",
        "Cyber security guidance",
        "New cyber security controls for institutions.",
        8,
        19,
        "https://security.example/guidance",
    ),
    EvaluationDocument(
        "e09",
        "github",
        "Quantum sensor toolkit",
        "Rare quantum sensor calibration utilities.",
        48,
        9,
        "https://github.com/lab/quantum-sensor",
    ),
    EvaluationDocument(
        "e10",
        "gdelt",
        "Baghdad regional summit",
        "Delegations meet in Baghdad for a regional summit.",
        6,
        30,
        "https://wire.example/baghdad-summit",
    ),
    EvaluationDocument(
        "e11",
        "rss",
        "Iraq investment outlook",
        "Institutional analysis of Iraq investment conditions.",
        18,
        23,
        "https://finance.example/iraq",
    ),
    EvaluationDocument(
        "e12",
        "rss",
        "Oil market outlook",
        "Oil market prices and supply analysis.",
        3,
        92,
        "https://markets.example/oil",
    ),
    EvaluationDocument(
        "e13",
        "gdelt",
        "Apple harvest forecast",
        "Agriculture outlook for apple growers.",
        5,
        40,
        "https://farm.example/apple",
    ),
    EvaluationDocument(
        "e14",
        "github",
        "Apple privacy controls",
        "Software project tracking Apple platform privacy controls.",
        24,
        28,
        "https://github.com/example/apple-privacy",
    ),
    EvaluationDocument(
        "e15",
        "rss",
        "Artificial intelligence governance",
        "Public-sector artificial intelligence governance framework.",
        9,
        17,
        "https://policy.example/ai",
    ),
    EvaluationDocument(
        "e16",
        "gdelt",
        "Health ministry briefing",
        "The health ministry published hospital capacity data.",
        7,
        21,
        "https://health.example/briefing",
    ),
    EvaluationDocument(
        "e17",
        "hacker_news",
        "Football climate campaign",
        "A popular football campaign briefly mentions climate.",
        1,
        100,
        "https://sport.example/campaign",
    ),
    EvaluationDocument(
        "a01",
        "rss",
        "وزارة الصحة تعلن خطة جديدة",
        "خطة وزارة الصحة لتحسين خدمات المستشفيات.",
        4,
        11,
        "https://ar.example/health",
    ),
    EvaluationDocument(
        "a02",
        "gdelt",
        "وزارة التعليم تعلن نتائج الامتحانات",
        "تفاصيل نتائج الطلبة لهذا العام.",
        3,
        70,
        "https://ar.example/education",
    ),
    EvaluationDocument(
        "a03",
        "bluesky",
        "مرصد العراق ينشر تقريره",
        "تقرير مرصد العراق عن المحتوى العام.",
        2,
        22,
        "https://bsky.app/profile/example/post/1",
    ),
    EvaluationDocument(
        "a04",
        "rss",
        "العراق وتغير المناخ",
        "سياسة العراق لمواجهة تغير المناخ.",
        15,
        15,
        "https://ar.example/climate",
    ),
    EvaluationDocument(
        "a05",
        "gdelt",
        "مؤتمر بغداد الاقليمي",
        "اجتماع وفود في مؤتمر بغداد الاقليمي.",
        6,
        35,
        "https://ar.example/baghdad",
    ),
    EvaluationDocument(
        "a06",
        "github",
        "ادوات الامن السيبراني",
        "مشروع مفتوح لدعم الامن السيبراني للمؤسسات.",
        20,
        18,
        "https://github.com/example/arabic-security",
    ),
    EvaluationDocument(
        "a07",
        "rss",
        "حوكمة الذكاء الاصطناعي",
        "اطار حوكمة الذكاء الاصطناعي في القطاع العام.",
        10,
        20,
        "https://ar.example/ai",
    ),
    EvaluationDocument(
        "a08",
        "gdelt",
        "مشروعات الطاقة المتجددة",
        "توسع مشروعات الطاقة المتجددة في العراق.",
        8,
        27,
        "https://ar.example/energy",
    ),
    EvaluationDocument(
        "a09",
        "rss",
        "مؤتمر بغداد الاقليمي",
        "اجتماع وفود في مؤتمر بغداد الاقليمي.",
        7,
        8,
        "https://ar.example/baghdad?ref=home",
    ),
    EvaluationDocument(
        "a10",
        "rss",
        "عين على الاقتصاد",
        "برنامج اقتصادي اسبوعي لا يتعلق بالصحة.",
        1,
        88,
        "https://ar.example/economy",
    ),
    EvaluationDocument(
        "m01",
        "github",
        "MIRSAD Iraq localization",
        "Arabic العراق localization resources for MIRSAD.",
        5,
        13,
        "https://github.com/example/mirsad-iq",
    ),
    EvaluationDocument(
        "m02",
        "rss",
        "MIRSAD product review",
        "Unrelated commercial product called MIRSAD.",
        2,
        75,
        "https://review.example/mirsad",
    ),
    EvaluationDocument(
        "e18",
        "rss",
        "Public procurement transparency",
        "New public procurement transparency register.",
        11,
        16,
        "https://gov.example/procurement",
    ),
)

HARD_DOCUMENTS = DOCUMENTS + (
    EvaluationDocument(
        "h01",
        "x",
        "Open source celebrity fashion",
        "A viral entertainment post with no software or licensing discussion.",
        1,
        100,
        "https://social.example/fashion",
    ),
    EvaluationDocument(
        "h02",
        "github",
        "Institutional software release",
        "Maintainers published an open source licensing and governance update.",
        240,
        2,
        "https://github.com/institution/release",
    ),
    EvaluationDocument(
        "h03",
        "x",
        "Artificial intelligence conference catering",
        "A popular post about venue logistics, menus, and ticket queues.",
        1,
        100,
        "https://social.example/conference",
    ),
    EvaluationDocument(
        "h04",
        "rss",
        "Policy memo",
        "A detailed artificial intelligence governance framework for public bodies.",
        336,
        1,
        "https://policy.example/ai-governance-memo",
    ),
    EvaluationDocument(
        "h05",
        "telegram",
        "الصحة الرقمية في العراق",
        "تحديث تقني عام لا يتضمن إعلانا من وزارة الصحة.",
        1,
        95,
        "https://t.me/public/5",
    ),
    EvaluationDocument(
        "h06",
        "telegram",
        "تحديث من بغداد",
        "معلومات عامة للخدمات في المدينة #بغداد",
        3,
        18,
        "https://t.me/public/6",
        hashtags=("بغداد",),
    ),
    EvaluationDocument(
        "h07",
        "rss",
        "بغداديات ثقافية",
        "برنامج ثقافي أسبوعي.",
        2,
        40,
        "https://ar.example/culture",
    ),
    EvaluationDocument(
        "h08",
        "x",
        "Public update",
        "A status from the institutional analyst account.",
        2,
        12,
        "https://x.com/analyst/status/8",
        author_handle="analyst",
    ),
    EvaluationDocument(
        "h09",
        "rss",
        "Regional data bulletin",
        "The open data portal published a machine-readable procurement dataset.",
        72,
        3,
        "https://data.example/bulletin",
    ),
    EvaluationDocument(
        "h10",
        "x",
        "Open debate on a new portal",
        "The unrelated post places data hundreds of words away from the original context.",
        1,
        99,
        "https://social.example/debate",
    ),
)

HARD_QUERY_JUDGMENTS = (
    ("climate", False, {"e01", "e02"}),
    ('"climate policy"', False, {"e01", "e02"}),
    ("open source", False, {"h02"}),
    ("artificial intelligence governance", False, {"e15", "h04"}),
    ("وزارة الصحة", True, {"a01"}),
    ("وِزَارَةُ الصِّحَّة", False, {"a01"}),
    ("#بغداد", False, {"h06"}),
    ("@analyst", False, {"h08"}),
    ("MIRSAD العراق", False, {"m01"}),
    ("open data portal", True, {"e06", "e07", "h09"}),
    ("Iraq investment", False, {"e11"}),
    ("Acme Organization", True, {"e04"}),
    ("Apple", False, {"e13", "e14"}),
    ("الامن السيبراني", False, {"a06"}),
    ("quantum sensor", False, {"e09"}),
    ("مصطلح نادر غير موجود", False, set()),
)


QUERY_JUDGMENTS = (
    ("climate policy", False, {"e01", "e02"}),
    ("Climate Policy", True, {"e01", "e02"}),
    ("Acme Organization", True, {"e04"}),
    ("open data portal", True, {"e06", "e07"}),
    ("cyber security", False, {"e08"}),
    ("quantum sensor", False, {"e09"}),
    ("Baghdad summit", False, {"e10"}),
    ("Iraq investment", False, {"e11"}),
    ("oil market", True, {"e12"}),
    ("Apple", False, {"e13", "e14"}),
    ("artificial intelligence governance", False, {"e15"}),
    ("health ministry", False, {"e16"}),
    ("وزارة الصحة", True, {"a01"}),
    ("وزاره الصحه", False, {"a01"}),
    ("مرصد العراق", True, {"a03"}),
    ("تغير المناخ", False, {"a04"}),
    ("مؤتمر بغداد", True, {"a05", "a09"}),
    ("الامن السيبراني", False, {"a06"}),
    ("الذكاء الاصطناعي", False, {"a07"}),
    ("MIRSAD العراق", False, {"m01"}),
)


def _legacy_final_score(document: EvaluationDocument, processed, *, coverage: float) -> float:
    normalized_title = normalize_text(document.title)
    combined = normalize_text(f"{document.title} {document.text}")
    title_tokens = set(tokenize(normalized_title))
    title_coverage = sum(token in title_tokens for token in processed.tokens) / max(
        1, len(processed.tokens)
    )
    relevance = min(
        100,
        35 * coverage
        + 20 * title_coverage
        + 20 * float(processed.normalized in combined)
        + 15 * coverage
        + 10 * float(coverage == 1),
    )
    values = {
        "relevance": relevance,
        "freshness": freshness_score(
            EVALUATION_NOW - timedelta(hours=document.age_hours), now=EVALUATION_NOW
        ),
        "engagement": document.engagement,
        "source_confidence": 70,
        "cross_source_presence": 0,
        "novelty": 100,
    }
    return round(
        sum(DEFAULT_WEIGHTS[key] * value for key, value in values.items())
        - spam_penalty(document.title, document.text, document.url),
        2,
    )


def _production_score(document: EvaluationDocument, processed, coverage: float):
    return calculate_score(
        query=processed,
        title=document.title,
        text=document.text,
        canonical_url=document.url,
        published_at=EVALUATION_NOW - timedelta(hours=document.age_hours),
        engagement=document.engagement,
        source_confidence=70,
        bm25_normalized=coverage * 100,
        author_handle=document.author_handle,
        hashtags=document.hashtags,
        weights=DEFAULT_WEIGHTS,
        now=EVALUATION_NOW,
    )


def _scored(
    query: str,
    exact: bool,
    *,
    documents: tuple[EvaluationDocument, ...] = DOCUMENTS,
    baseline: bool = False,
) -> list[tuple[str, float, Any | None]]:
    processed = process_query(query, exact_phrase=exact)
    scored: list[tuple[str, float, Any | None]] = []
    for document in documents:
        combined = normalize_text(f"{document.title} {document.text}")
        tokens = set(tokenize(combined))
        coverage = len(tokens & set(processed.tokens)) / max(1, len(processed.tokens))
        eligible = (
            coverage > 0 and (not processed.exact_phrase or processed.normalized in combined)
            if baseline
            else is_candidate_match(
                processed,
                document.title,
                document.text,
                canonical_url=document.url,
                author_handle=document.author_handle,
                hashtags=document.hashtags,
            )
        )
        if not eligible:
            continue
        score = (
            _legacy_final_score(document, processed, coverage=coverage)
            if baseline
            else _production_score(document, processed, coverage)
        )
        scored.append(
            (document.id, score if baseline else score.final_score, None if baseline else score)
        )
    return sorted(scored, key=lambda item: (item[1], item[0]), reverse=True)


def _rank(
    query: str,
    exact: bool,
    *,
    documents: tuple[EvaluationDocument, ...] = DOCUMENTS,
    baseline: bool = False,
) -> list[str]:
    return [
        document_id
        for document_id, _score, _components in _scored(
            query, exact, documents=documents, baseline=baseline
        )
    ]


def _controlled_score(*, title: str, text: str, age_hours: int = 12, engagement: float = 20):
    return calculate_score(
        query=process_query("public policy"),
        title=title,
        text=text,
        canonical_url="https://evaluation.example/controlled",
        published_at=EVALUATION_NOW - timedelta(hours=age_hours),
        engagement=engagement,
        source_confidence=70,
        bm25_normalized=75,
        weights=DEFAULT_WEIGHTS,
        now=EVALUATION_NOW,
    )


def _signal_checks() -> dict[str, Any]:
    title_match = _controlled_score(
        title="Public policy briefing",
        text="Detailed institutional analysis for the controlled evaluation.",
    )
    text_match = _controlled_score(
        title="Institutional briefing",
        text="Detailed public policy analysis for the controlled evaluation.",
    )
    recent = _controlled_score(title="Public policy", text="Controlled analysis.", age_hours=1)
    old = _controlled_score(title="Public policy", text="Controlled analysis.", age_hours=720)
    engaged = _controlled_score(title="Public policy", text="Controlled analysis.", engagement=90)
    quiet = _controlled_score(title="Public policy", text="Controlled analysis.", engagement=5)
    climate_ranked = _rank("climate policy", False)
    return {
        "title_boost_relevance_delta": round(title_match.relevance - text_match.relevance, 2),
        "freshness_final_score_delta": round(recent.final_score - old.final_score, 2),
        "engagement_final_score_delta": round(engaged.final_score - quiet.final_score, 2),
        "relevant_beats_high_engagement_collision": "e17" not in climate_ranked
        or climate_ranked.index("e01") < climate_ranked.index("e17"),
        "irrelevant_collision_excluded": "e17" not in climate_ranked,
    }


def _evaluate_cases(judgments, documents, *, baseline: bool = False) -> list[dict[str, Any]]:
    cases = []
    for query, exact, relevant in judgments:
        ranked = _rank(query, exact, documents=documents, baseline=baseline)
        metrics: dict[str, float] = {}
        for cutoff in (5, 10):
            considered = ranked[:cutoff]
            matches = len(set(considered) & relevant)
            metrics[f"precision_at_{cutoff}"] = round(matches / cutoff, 4)
            metrics[f"returned_set_precision_at_{cutoff}"] = round(
                matches / max(1, len(considered)), 4
            )
            metrics[f"strict_precision_at_{cutoff}"] = metrics[f"precision_at_{cutoff}"]
        first = next((index for index, item in enumerate(ranked, 1) if item in relevant), None)
        metrics["reciprocal_rank"] = round(1 / first, 4) if first else 0.0
        cases.append(
            {
                "query": query,
                "exact_phrase": exact,
                "relevant": sorted(relevant),
                "ranked": ranked[:10],
                "no_result_success": not ranked and not relevant,
                **metrics,
            }
        )
    return cases


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, float]:
    applicable = [case for case in cases if case["relevant"]]
    return {
        "mean_precision_at_5": round(mean(case["precision_at_5"] for case in applicable), 4),
        "mean_precision_at_10": round(mean(case["precision_at_10"] for case in applicable), 4),
        "mean_returned_set_precision_at_5": round(
            mean(case["returned_set_precision_at_5"] for case in applicable), 4
        ),
        "mean_returned_set_precision_at_10": round(
            mean(case["returned_set_precision_at_10"] for case in applicable), 4
        ),
        "mean_strict_precision_at_5": round(
            mean(case["strict_precision_at_5"] for case in applicable), 4
        ),
        "mean_strict_precision_at_10": round(
            mean(case["strict_precision_at_10"] for case in applicable), 4
        ),
        "mean_reciprocal_rank": round(mean(case["reciprocal_rank"] for case in applicable), 4),
    }


def _language_metrics(cases: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict[str, Any]]] = {"arabic": [], "english": [], "mixed": []}
    for case in cases:
        query = case["query"]
        has_arabic = any("\u0600" <= character <= "\u06ff" for character in query)
        has_latin = any(character.isascii() and character.isalpha() for character in query)
        group = "mixed" if has_arabic and has_latin else "arabic" if has_arabic else "english"
        groups[group].append(case)
    return {name: _aggregate(values) for name, values in groups.items() if values}


def _error_analysis(cases: list[dict[str, Any]], documents) -> list[dict[str, Any]]:
    by_id = {document.id: document for document in documents}
    errors: list[dict[str, Any]] = []
    for case in cases:
        top = case["ranked"][:5]
        relevant = set(case["relevant"])
        for missing in sorted(relevant - set(top)):
            errors.append({"query": case["query"], "document": missing, "category": "LEXICAL_MISS"})
        for identifier in top:
            if identifier in relevant:
                continue
            document = by_id[identifier]
            query_tokens = set(tokenize(case["query"]))
            title_tokens = set(tokenize(document.title))
            category = (
                "ENGAGEMENT_OVERWEIGHTED"
                if document.engagement >= 80
                else "TITLE_OVERWEIGHTED"
                if query_tokens and query_tokens.issubset(title_tokens)
                else "AMBIGUOUS_QUERY"
            )
            errors.append({"query": case["query"], "document": identifier, "category": category})
    return errors


def _component_statistics() -> dict[str, dict[str, float]]:
    values: dict[str, list[float]] = {
        key: []
        for key in (
            "final_score",
            "relevance",
            "freshness",
            "engagement",
            "source_confidence",
            "cross_source_presence",
            "novelty",
            "spam_penalty",
        )
    }
    for query, exact, _relevant in HARD_QUERY_JUDGMENTS:
        for _identifier, _final, score in _scored(query, exact, documents=HARD_DOCUMENTS):
            for field in values:
                values[field].append(float(getattr(score, field)))
    output = {}
    for field, samples in values.items():
        ordered = sorted(samples)
        output[field] = {
            "min": round(min(samples), 2),
            "max": round(max(samples), 2),
            "mean": round(mean(samples), 2),
            "median": round(median(samples), 2),
            "stddev": round(pstdev(samples), 2),
            "p10": round(_percentile(ordered, 0.10), 2),
            "p25": round(_percentile(ordered, 0.25), 2),
            "p75": round(_percentile(ordered, 0.75), 2),
            "p90": round(_percentile(ordered, 0.90), 2),
        }
    return output


def _percentile(ordered: list[float], ratio: float) -> float:
    index = min(len(ordered) - 1, int(ratio * (len(ordered) - 1)))
    return ordered[index]


def evaluate_search_quality() -> dict[str, Any]:
    cases = _evaluate_cases(QUERY_JUDGMENTS, DOCUMENTS)
    baseline_cases = _evaluate_cases(QUERY_JUDGMENTS, DOCUMENTS, baseline=True)
    hard_cases = _evaluate_cases(HARD_QUERY_JUDGMENTS, HARD_DOCUMENTS)
    hard_baseline_cases = _evaluate_cases(HARD_QUERY_JUDGMENTS, HARD_DOCUMENTS, baseline=True)

    dedupe_items = [
        DeduplicationItem(
            key=index,
            source=document.source,
            canonical_url=document.url,
            title=document.title,
            text=document.text,
            published_at=EVALUATION_NOW - timedelta(hours=document.age_hours),
        )
        for index, document in enumerate(DOCUMENTS)
    ]
    groups = find_duplicate_groups(dedupe_items)
    clusters = cluster_items(dedupe_items)
    duplicate_records = sum(len(group.members) - 1 for group in groups)
    expected_duplicate_pairs = {
        frozenset((index, other_index))
        for index, document in enumerate(DOCUMENTS)
        for other_index, other in enumerate(DOCUMENTS[index + 1 :], index + 1)
        if {document.id, other.id} in ({"e01", "e02"}, {"a05", "a09"})
    }
    document_indexes = {document.id: index for index, document in enumerate(DOCUMENTS)}
    expected_cluster_pairs = expected_duplicate_pairs | {
        frozenset((document_indexes["e06"], document_indexes["e07"]))
    }
    duplicate_pairs = {
        frozenset((left, right))
        for group in groups
        for position, left in enumerate(group.members)
        for right in group.members[position + 1 :]
    }
    cluster_pairs = {
        frozenset((left, right))
        for cluster in clusters
        for position, left in enumerate(cluster.members)
        for right in cluster.members[position + 1 :]
    }

    def pair_quality(
        predicted: set[frozenset[int]], expected: set[frozenset[int]]
    ) -> dict[str, float]:
        true_positive = len(predicted & expected)
        return {
            "precision": round(true_positive / max(1, len(predicted)), 4),
            "recall": round(true_positive / max(1, len(expected)), 4),
        }

    exact_cases = [case for case in cases if case["exact_phrase"]]
    aggregate = _aggregate(cases)
    return {
        "suite": "mirsad-search-quality",
        "version": "2.0",
        "fixture_records": len(DOCUMENTS),
        "query_count": len(cases),
        "metrics": {
            **aggregate,
            "duplicate_records_detected": duplicate_records,
            "duplicate_reduction_rate": round(duplicate_records / len(DOCUMENTS), 4),
            "duplicate_pair_quality": pair_quality(duplicate_pairs, expected_duplicate_pairs),
            "cluster_pair_quality": pair_quality(cluster_pairs, expected_cluster_pairs),
            "exact_phrase_cases": len(exact_cases),
            "exact_phrase_mean_precision_at_5": round(
                mean(case["precision_at_5"] for case in exact_cases), 4
            ),
            "exact_phrase_mean_returned_set_precision_at_5": round(
                mean(case["returned_set_precision_at_5"] for case in exact_cases), 4
            ),
        },
        "baseline_metrics": _aggregate(baseline_cases),
        "language_metrics": _language_metrics(cases),
        "hard_evaluation": {
            "fixture_records": len(HARD_DOCUMENTS),
            "query_count": len(hard_cases),
            "baseline_metrics": _aggregate(hard_baseline_cases),
            "metrics": _aggregate(hard_cases),
            "error_analysis": _error_analysis(hard_cases, HARD_DOCUMENTS),
            "cases": hard_cases,
        },
        "score_component_statistics": _component_statistics(),
        "signal_checks": _signal_checks(),
        "cases": cases,
    }
