from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mirsad_api.config import Settings
from mirsad_api.connectors import (
    BaseConnector,
    ConnectorDiagnostics,
    ConnectorError,
    ConnectorItem,
    ConnectorSearchOptions,
    ConnectorValidation,
)
from mirsad_api.database import init_database, make_engine
from mirsad_api.domains.semantic import SemanticRanker, build_semantic_ranker
from mirsad_api.models import ContentItem, ContentScore, SearchResult
from mirsad_api.schemas import SearchRequest, TimeRange
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.registry import build_connector_registry
from mirsad_api.services.search import SearchService

OUTPUT = Path("reports/production-evidence")
CAPTURE_QUERIES = (
    "بغداد",
    "العراق",
    "الذكاء الاصطناعي",
    "وزارة التخطيط",
    "التكنولوجيا",
    "#بغداد",
    "artificial intelligence",
    "open source",
    "climate adaptation",
    "public health",
    "technology",
    "#technology",
    "AI العراق",
    "Microsoft العراق",
    "OpenAI بغداد",
)
CAPTURE_SOURCES = ("bluesky", "youtube", "mastodon", "github", "hacker_news", "rss")
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
LATIN_RE = re.compile(r"[A-Za-z]")
TOKEN_RE = re.compile(r"[#@]?[\w\u0600-\u06ff][\w\u0600-\u06ff._/-]*", re.UNICODE)
IDENTIFIER_RE = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,7}|GHSA-[0-9A-Za-z-]{14,}|CWE-\d+|[0-9a-f]{12,40})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class KnownItemCase:
    case_id: str
    source: str
    target_external_id: str
    target_url: str
    query: str
    query_class: str
    language: str
    exact_phrase: bool
    capture_query: str


class ReplayConnector(BaseConnector):
    """Replay one real connector response through the normal content pipeline."""

    def __init__(self, original: BaseConnector, items: list[ConnectorItem]) -> None:
        self.metadata = original.metadata
        super().__init__(timeout=original.timeout, retries=0)
        self.items = items

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, "real response replay"

    async def validate_access(self) -> ConnectorValidation:
        return ConnectorValidation("pass", "real_response", "Real response captured")

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        del query, since
        items = self.items[:limit]
        self.last_diagnostics = ConnectorDiagnostics(
            http_status=200,
            attempt_count=1,
            raw_result_count=len(items),
            fetched_result_count=len(items),
            schema_valid_count=len(items),
            query_match_count=len(items),
            time_eligible_count=len(items),
            normalized_result_count=len(items),
            details={"production_evidence_replay": True},
        )
        return items

    def normalize(self, payload: dict[str, Any]) -> ConnectorItem:
        raise NotImplementedError("ReplayConnector receives normalized real records")


def _language(text: str, hint: str = "und") -> str:
    has_arabic = bool(ARABIC_RE.search(text))
    has_latin = bool(LATIN_RE.search(text))
    if has_arabic and has_latin:
        return "mixed"
    if has_arabic:
        return "arabic"
    if has_latin:
        return "english"
    return "arabic" if hint == "ar" else "english" if hint == "en" else "unknown"


def _item_payload(item: ConnectorItem, capture_query: str) -> dict[str, Any]:
    text = f"{item.title or ''} {item.text}".strip()
    return {
        "capture_query": capture_query,
        "capture_timestamp": datetime.now(UTC).isoformat(),
        "source": item.source,
        "acquisition_mode": item.acquisition_mode.value,
        "external_id": item.external_id,
        "canonical_url": item.canonical_url,
        "author": item.author,
        "author_handle": item.author_handle,
        "title": item.title,
        "text": item.text,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "fetched_at": item.fetched_at.isoformat(),
        "language": _language(text, item.language),
        "source_language": item.language,
        "hashtags": list(item.hashtags or ()),
        "mentions": list(item.mentions or ()),
        "media_type": item.media_type,
        "raw_metrics": item.raw_metrics,
        "raw_metadata": item.raw_metadata,
    }


def _distinctive_phrase(item: dict[str, Any]) -> str | None:
    for value in (item.get("title"), item.get("text")):
        tokens = [token for token in TOKEN_RE.findall(str(value or "")) if len(token) > 1]
        if len(tokens) >= 4:
            return " ".join(tokens[: min(8, len(tokens))])
    return None


def _known_query(item: dict[str, Any]) -> tuple[str, str, bool] | None:
    body = f"{item.get('title') or ''} {item.get('text') or ''}"
    identifier = IDENTIFIER_RE.search(body)
    if identifier:
        return identifier.group(0), "identifier", False
    hashtags = [str(value).strip().removeprefix("#") for value in item.get("hashtags") or []]
    if hashtags and len(hashtags[0]) >= 3:
        return f"#{hashtags[0]}", "hashtag", False
    handle = str(item.get("author_handle") or "").strip().removeprefix("@")
    if len(handle) >= 4 and re.fullmatch(r"[\w.:-]+", handle, re.UNICODE):
        return f"@{handle}", "handle", False
    phrase = _distinctive_phrase(item)
    if phrase:
        return phrase, "exact_phrase", True
    return None


def select_known_cases(
    records: list[dict[str, Any]], *, maximum: int
) -> list[KnownItemCase]:
    buckets: dict[str, list[KnownItemCase]] = defaultdict(list)
    seen_queries: set[tuple[str, str, str]] = set()
    for record in records:
        query = _known_query(record)
        if query is None:
            continue
        text, query_class, exact = query
        identity = (str(record["source"]), text.casefold(), str(record["canonical_url"]))
        if identity in seen_queries:
            continue
        seen_queries.add(identity)
        digest = hashlib.sha256(
            f"{record['source']}\0{record['canonical_url']}\0{text}".encode()
        ).hexdigest()[:16]
        language = str(record.get("language") or "unknown")
        buckets[language].append(
            KnownItemCase(
                case_id=f"real-{digest}",
                source=str(record["source"]),
                target_external_id=str(record["external_id"]),
                target_url=str(record["canonical_url"]),
                query=text,
                query_class=query_class,
                language=language,
                exact_phrase=exact,
                capture_query=str(record["capture_query"]),
            )
        )
    targets = {
        "arabic": min(30, maximum),
        "english": min(45, maximum),
        "mixed": min(15, maximum),
    }
    selected: list[KnownItemCase] = []
    for language in ("arabic", "english", "mixed"):
        selected.extend(buckets[language][: targets[language]])
    leftovers = [
        case
        for language in sorted(buckets)
        for case in buckets[language]
        if case not in selected
    ]
    selected.extend(leftovers[: max(0, maximum - len(selected))])
    return selected[:maximum]


def assert_target_not_in_memory(db: Session, target_url: str) -> None:
    existing = db.scalar(select(ContentItem.id).where(ContentItem.canonical_url == target_url))
    if existing is not None:
        raise RuntimeError("Known-item target was present before live response admission")


def known_item_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [case for case in cases if case.get("live_request_completed")]
    ranks = [case.get("final_rank") for case in evaluated]

    def recall(k: int) -> float:
        return round(sum(rank is not None and rank <= k for rank in ranks) / max(1, len(ranks)), 4)

    return {
        "cases": len(evaluated),
        "known_item_recall_at_1": recall(1),
        "known_item_recall_at_5": recall(5),
        "known_item_recall_at_10": recall(10),
        "known_item_recall_at_20": recall(20),
        "known_item_mrr": round(
            sum(1 / rank for rank in ranks if rank is not None) / max(1, len(ranks)), 4
        ),
        "known_item_success_at_5": recall(5),
        "known_item_success_at_10": recall(10),
    }


def grouped_known_item_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for field in ("language", "source", "query_class"):
        for value in sorted({str(case.get(field, "unknown")) for case in cases}):
            members = [case for case in cases if str(case.get(field, "unknown")) == value]
            groups[f"{field}:{value}"] = {
                "captured_cases": len(members),
                "external_limits": sum(not case.get("live_request_completed") for case in members),
                **known_item_metrics(members),
            }
    return groups


async def _capture(
    registry: dict[str, BaseConnector], *, per_query_limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    telemetry: list[dict[str, Any]] = []
    semaphore = asyncio.Semaphore(6)

    async def one(source: str, query: str) -> None:
        connector = registry[source]
        started = perf_counter()
        async with semaphore:
            try:
                items = await connector.search_with_options(
                    query,
                    limit=per_query_limit,
                    since=None,
                    options=ConnectorSearchOptions(
                        original_query=query,
                        query_variants=(query,),
                        search_mode="balanced",
                        time_range="all",
                    ),
                )
                state = "LIVE"
                error = None
            except ConnectorError as exc:
                items = []
                state = "EXTERNAL_LIMIT" if exc.code in {
                    "rate_limited",
                    "quota_exhausted",
                    "http_403",
                    "timeout",
                    "dns_network",
                } else "CONNECTOR_ERROR"
                error = exc.code
            diagnostic = connector.last_diagnostics
            telemetry.append(
                {
                    "source": source,
                    "query": query,
                    "state": state,
                    "error": error,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "fetched": diagnostic.fetched_result_count or diagnostic.raw_result_count,
                    "valid": diagnostic.schema_valid_count,
                    "matching": diagnostic.query_match_count,
                    "normalized": diagnostic.normalized_result_count or len(items),
                    "returned": len(items),
                    "http_status": diagnostic.http_status,
                }
            )
            for item in items:
                records.setdefault((item.source, item.canonical_url), _item_payload(item, query))

    await asyncio.gather(
        *(one(source, query) for query in CAPTURE_QUERIES for source in CAPTURE_SOURCES)
    )
    return list(records.values()), telemetry


async def _live_response_for_case(
    connector: BaseConnector, case: KnownItemCase, *, limit: int
) -> tuple[list[ConnectorItem], dict[str, Any]]:
    started = perf_counter()
    try:
        items = await connector.search_with_options(
            case.query,
            limit=limit,
            since=None,
            options=ConnectorSearchOptions(
                exact_phrase=case.exact_phrase,
                original_query=case.query,
                query_variants=(case.query,),
                query_intent=case.query_class,
                time_range="all",
                search_mode="fast",
            ),
        )
        state = "LIVE"
        error = None
    except ConnectorError as exc:
        items = []
        state = "EXTERNAL_LIMIT" if exc.code in {
            "rate_limited",
            "quota_exhausted",
            "http_403",
            "timeout",
            "dns_network",
        } else "CONNECTOR_ERROR"
        error = exc.code
    diagnostic = connector.last_diagnostics
    return items, {
        "state": state,
        "error": error,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "fetched": diagnostic.fetched_result_count or diagnostic.raw_result_count,
        "valid": diagnostic.schema_valid_count,
        "matching": diagnostic.query_match_count,
        "normalized": diagnostic.normalized_result_count or len(items),
        "http_status": diagnostic.http_status,
    }


async def _evaluate_case(
    settings: Settings,
    connector: BaseConnector,
    semantic_ranker: SemanticRanker,
    case: KnownItemCase,
) -> dict[str, Any]:
    live_items, live = await _live_response_for_case(connector, case, limit=30)
    target_live = next(
        (
            item
            for item in live_items
            if item.canonical_url == case.target_url
            or item.external_id == case.target_external_id
        ),
        None,
    )
    if live["state"] != "LIVE":
        return {**asdict(case), **live, "live_request_completed": False, "final_rank": None}

    engine = make_engine("sqlite:///:memory:")
    init_database(engine)
    with Session(engine, expire_on_commit=False) as db:
        assert_target_not_in_memory(db, case.target_url)
        replay = ReplayConnector(connector, live_items)
        seed_database(db, {case.source: replay})
        service = SearchService(
            db,
            settings,
            {case.source: replay},
            semantic_ranker=semantic_ranker,
        )
        session_id = await service.execute(
            SearchRequest(
                query=case.query,
                sources=[case.source],
                source_selection="explicit",
                search_mode="fast",
                exact_phrase=case.exact_phrase,
                time_range=TimeRange.ALL,
                limit=30,
            )
        )
        target_row = db.scalar(
            select(ContentItem).where(
                (ContentItem.canonical_url == case.target_url)
                | (ContentItem.external_id == case.target_external_id)
            )
        )
        rank = None
        semantic_opportunity = False
        score = None
        if target_row is not None:
            result = db.scalar(
                select(SearchResult).where(
                    SearchResult.search_session_id == session_id,
                    SearchResult.content_item_id == target_row.id,
                )
            )
            rank = result.rank if result else None
            score_row = db.scalar(
                select(ContentScore).where(
                    ContentScore.search_session_id == session_id,
                    ContentScore.content_item_id == target_row.id,
                )
            )
            if score_row:
                explanation = score_row.explanation or {}
                semantic_opportunity = explanation.get("semantic_relevance") is not None
                score = score_row.final_score
        from mirsad_api.models import SearchSession

        session = db.get(SearchSession, session_id)
        diagnostics = session.diagnostics or {} if session else {}
        connector_diagnostic = (diagnostics.get("connectors") or [{}])[0]
        result = {
            **asdict(case),
            **live,
            "live_request_completed": True,
            "live_returned": len(live_items),
            "discovered": target_live is not None,
            "canonicalized": (
                target_live is not None and target_live.canonical_url == case.target_url
            ),
            "matched": bool(
                target_row is not None
                or target_live is not None
                and connector_diagnostic.get("final_matching_results", 0) > 0
            ),
            "admitted": target_row is not None,
            "semantic_opportunity": semantic_opportunity,
            "final_rank": rank,
            "final_score": score,
            "session_status": session.status if session else "unknown",
            "pipeline_latency_ms": session.duration_ms if session else None,
            "stop_reason": diagnostics.get("mafer", {}).get("stop_reason")
            or diagnostics.get("search_trace", {}).get("stop_reason")
            or diagnostics.get("stop_reason"),
            "production_shadow": diagnostics.get("mafer", {}).get("shadow_ranking")
            or diagnostics.get("search_trace", {}).get("shadow_ranking")
            or diagnostics.get("shadow_ranking"),
        }
    engine.dispose()
    return result


def _arabic_funnel(cases: list[dict[str, Any]]) -> dict[str, Any]:
    arabic = [case for case in cases if case.get("language") in {"arabic", "mixed"}]
    stages = (
        "live_request_completed",
        "discovered",
        "canonicalized",
        "matched",
        "admitted",
        "semantic_opportunity",
    )
    counts = {
        stage: sum(
            bool(
                case.get(stage)
                or (
                    stage == "semantic_opportunity"
                    and case.get("admitted")
                    and case.get("query_class") in {"handle", "hashtag", "identifier"}
                )
            )
            for case in arabic
        )
        for stage in stages
    }
    counts["final_top_5"] = sum(
        case.get("final_rank") is not None and case["final_rank"] <= 5 for case in arabic
    )
    counts["final_top_10"] = sum(
        case.get("final_rank") is not None and case["final_rank"] <= 10 for case in arabic
    )
    misses = []
    for case in arabic:
        loss = next(
            (
                stage
                for stage in stages
                if not case.get(stage)
                and not (
                    stage == "semantic_opportunity"
                    and case.get("admitted")
                    and case.get("query_class") in {"handle", "hashtag", "identifier"}
                )
            ),
            None,
        )
        if loss is None and case.get("final_rank") is None:
            loss = "final_ranking"
        if loss:
            misses.append({"case_id": case["case_id"], "source": case["source"], "loss": loss})
    return {"known_targets": len(arabic), "stage_counts": counts, "misses": misses}


async def run(maximum_cases: int, per_query_limit: int) -> dict[str, Any]:
    settings = Settings(
        database_url="sqlite:///:memory:",
        semantic_candidate_limit=20,
        semantic_relevance_weight=0.75,
        semantic_quality_budget=0.01,
    )
    registry = build_connector_registry(settings)
    records, capture_telemetry = await _capture(registry, per_query_limit=per_query_limit)
    cases = select_known_cases(records, maximum=maximum_cases)
    semantic_ranker = build_semantic_ranker(settings)
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        evaluated.append(
            await _evaluate_case(settings, registry[case.source], semantic_ranker, case)
        )

    language_counts = Counter(record["language"] for record in records)
    source_counts = Counter(record["source"] for record in records)
    case_language_counts = Counter(case.language for case in cases)
    case_class_counts = Counter(case.query_class for case in cases)
    output = {
        "schema": "mirsad.production-real-data-evidence",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "production_configuration": {
            "planner": "mafer-planner-v2.0",
            "ranking": "mirsad-hybrid-lex25-sem75-v1",
            "semantic_model": settings.semantic_model_name,
            "semantic_model_version": settings.semantic_model_version,
            "semantic_candidate_limit": settings.semantic_candidate_limit,
            "lexical_weight": 0.25,
            "semantic_weight": settings.semantic_relevance_weight,
            "secondary_quality_budget": settings.semantic_quality_budget,
        },
        "network_budget": {
            "capture_queries": len(CAPTURE_QUERIES),
            "capture_sources": len(CAPTURE_SOURCES),
            "capture_request_limit": len(CAPTURE_QUERIES) * len(CAPTURE_SOURCES),
            "known_item_request_limit": len(cases),
            "records_per_capture_request": per_query_limit,
        },
        "corpus": {
            "records": len(records),
            "by_language": dict(language_counts),
            "by_source": dict(source_counts),
        },
        "known_item_cases": {
            "cases": len(cases),
            "by_language": dict(case_language_counts),
            "by_class": dict(case_class_counts),
            "metrics": known_item_metrics(evaluated),
        },
        "arabic_loss_funnel": _arabic_funnel(evaluated),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    corpus_path = OUTPUT / "real-corpus.json"
    cases_path = OUTPUT / "known-item-cases.json"
    evaluation_path = OUTPUT / "known-item-evaluation.json"
    telemetry_path = OUTPUT / "live-connector-telemetry.json"
    corpus_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    cases_path.write_text(
        json.dumps([asdict(case) for case in cases], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    evaluation_path.write_text(
        json.dumps(evaluated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    telemetry_path.write_text(
        json.dumps(capture_telemetry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (corpus_path, cases_path, evaluation_path, telemetry_path)
    }
    output["artifacts"] = hashes
    (OUTPUT / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect and evaluate bounded real MIRSAD evidence"
    )
    parser.add_argument("--max-cases", type=int, default=100)
    parser.add_argument("--per-query-limit", type=int, default=15)
    parser.add_argument("--summarize-existing", action="store_true")
    args = parser.parse_args()
    if args.summarize_existing:
        summary_path = OUTPUT / "summary.json"
        evaluation_path = OUTPUT / "known-item-evaluation.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        evaluated = json.loads(evaluation_path.read_text(encoding="utf-8"))
        payload["known_item_cases"]["metrics"] = known_item_metrics(evaluated)
        payload["arabic_loss_funnel"] = _arabic_funnel(evaluated)
        analysis = {
            "schema": "mirsad.production-known-item-analysis",
            "generated_at": datetime.now(UTC).isoformat(),
            "metrics_are_positive_only": True,
            "unjudged_results_are_not_labeled_irrelevant": True,
            "overall": known_item_metrics(evaluated),
            "groups": grouped_known_item_metrics(evaluated),
            "arabic_loss_funnel": payload["arabic_loss_funnel"],
        }
        (OUTPUT / "known-item-analysis.json").write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    maximum = max(1, min(args.max_cases, 100))
    per_query_limit = max(5, min(args.per_query_limit, 25))
    result = asyncio.run(run(maximum, per_query_limit))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
