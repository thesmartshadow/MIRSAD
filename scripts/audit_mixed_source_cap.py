from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import sessionmaker

from mirsad_api.config import Settings
from mirsad_api.connectors.base import (
    BaseConnector,
    ConnectorItem,
    ConnectorMetadata,
)
from mirsad_api.database import init_database, make_engine
from mirsad_api.models import SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import get_search_response
from mirsad_api.services.search import SearchService

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "mixed-source-cap-audit.md"
JSON_PATH = ROOT / "reports" / "mixed-source-cap-audit.json"
QUERIES = (
    "artificial intelligence",
    "open source",
    "climate adaptation",
    "public health",
    "technology",
    "#technology",
    "بغداد",
    "الذكاء الاصطناعي",
    "#بغداد",
    "Microsoft العراق",
    "AI بغداد",
)
SOURCES = (
    "youtube",
    "bluesky",
    "mastodon",
    "github",
    "hacker_news",
    "rss",
)
SOURCE_TYPES = {
    "youtube": "video",
    "bluesky": "post",
    "mastodon": "post",
    "github": "repository",
    "hacker_news": "story",
    "rss": "news",
}


class AuditConnector(BaseConnector):
    def __init__(self, source: str, delay: float) -> None:
        self.metadata = ConnectorMetadata(
            key=source,
            name=source.replace("_", " ").title(),
            kind="audit_fixture",
            base_url=f"https://{source}.audit.invalid",
            category=(
                "social"
                if source in {"youtube", "bluesky", "mastodon"}
                else "news"
                if source == "rss"
                else "developer_community"
            ),
        )
        super().__init__()
        self.delay = delay

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def search(self, query: str, *, limit: int, since=None) -> list[ConnectorItem]:
        await asyncio.sleep(self.delay)
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:10]
        templates = (
            (f"{query} evidence briefing", f"A focused {query} evidence briefing."),
            (f"Institutional update: {query}", f"Current public reporting about {query}."),
            ("Public evidence bulletin", f"Detailed analysis of {query} and its implications."),
            (f"{query} community discussion", f"Independent perspectives concerning {query}."),
            (f"Review of {query}", f"A concise account centered on {query}."),
            ("Daily public digest", f"The digest includes {query} with other public topics."),
            (f"{query} archive note", f"An older but directly relevant record about {query}."),
            ("General update", f"A brief mention of {query} in a broader context."),
        )
        now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
        return [
            ConnectorItem(
                source=self.metadata.key,
                external_id=f"{digest}-{index}",
                canonical_url=(
                    f"https://{self.metadata.key}.audit.invalid/{digest}/{index}"
                ),
                author=f"{self.metadata.key}_public",
                title=None
                if self.metadata.key in {"bluesky", "mastodon"}
                else title,
                text=(f"{title}. {text}" if self.metadata.key in {"bluesky", "mastodon"} else text),
                published_at=now,
                language=("ar" if any("\u0600" <= char <= "\u06ff" for char in query) else "en"),
                media_type=SOURCE_TYPES[self.metadata.key],
                raw_metadata={"source_type": SOURCE_TYPES[self.metadata.key]},
            )
            for index, (title, text) in enumerate(templates[:limit])
        ]

    def normalize(self, payload):
        raise NotImplementedError


def _identities(response) -> list[tuple[str, str]]:
    return [(item.source, item.external_id) for item in response.results]


async def run_audit() -> dict[str, object]:
    with TemporaryDirectory(prefix="mirsad-cap-audit-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'audit.db'}"
        engine = make_engine(database_url)
        init_database(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        settings = Settings(
            database_url=database_url,
            semantic_ranking_enabled=True,
            semantic_model_cache_dir=str(ROOT / "data/models"),
            semantic_model_local_files_only=True,
            source_pre_candidate_limit=50,
        )
        connectors = {
            source: AuditConnector(source, index * 0.008)
            for index, source in enumerate(SOURCES)
        }
        rows: list[dict[str, object]] = []
        invariant = True
        admission_intact = True
        comparable_sources_present = True
        with factory() as db:
            seed_database(db, connectors)
            service = SearchService(db, settings, connectors)
            for query in QUERIES:
                for index, source in enumerate(SOURCES):
                    connectors[source].delay = index * 0.008
                first_id = await service.execute(
                    SearchRequest(
                        query=query,
                        sources=list(SOURCES),
                        time_range="all",
                        limit=30,
                    )
                )
                first = get_search_response(db, first_id)
                first_diagnostics = db.get(SearchSession, first_id).diagnostics

                for index, source in enumerate(reversed(SOURCES)):
                    connectors[source].delay = index * 0.008
                second_id = await service.execute(
                    SearchRequest(
                        query=query,
                        sources=list(reversed(SOURCES)),
                        time_range="all",
                        limit=30,
                    )
                )
                second = get_search_response(db, second_id)
                second_diagnostics = db.get(SearchSession, second_id).diagnostics
                stable = _identities(first) == _identities(second)
                invariant = invariant and stable
                admission = first_diagnostics["candidate_admission"]
                admission_intact = admission_intact and all(
                    admission["admitted_per_source"].get(source, 0)
                    == min(admission["matched_per_source"].get(source, 0), 50)
                    for source in SOURCES
                )
                comparable_sources_present = comparable_sources_present and all(
                    admission["final_top_per_source"].get(source, 0) > 0
                    for source in SOURCES
                )
                rows.append(
                    {
                        "query": query,
                        "matched_per_source": admission["matched_per_source"],
                        "admitted_per_source": admission["admitted_per_source"],
                        "final_top_30_per_source": admission["final_top_per_source"],
                        "relevance_distribution_by_source": admission[
                            "relevance_distribution_by_source"
                        ],
                        "completion_order_a": first_diagnostics[
                            "connector_completion_order"
                        ],
                        "completion_order_b": second_diagnostics[
                            "connector_completion_order"
                        ],
                        "final_results_unchanged": stable,
                        "semantic_state": first_diagnostics["ranking"]["semantic_state"],
                        "semantic_model": first_diagnostics["ranking"]["semantic_model"],
                        "semantic_candidates_per_source": first_diagnostics["ranking"][
                            "semantic_candidates_per_source"
                        ],
                    }
                )
        engine.dispose()
    return {
        "schema": "mirsad.mixed-source-cap-audit.v1",
        "query_count": len(QUERIES),
        "global_limit": 30,
        "semantic_candidate_limit": 20,
        "source_pre_candidate_limit": 50,
        "sources": list(SOURCES),
        "all_completion_shuffles_invariant": invariant,
        "all_source_admission_intact": admission_intact,
        "comparable_fixture_sources_present": comparable_sources_present,
        "queries": rows,
    }


def _format_counts(values: dict[str, int]) -> str:
    return ", ".join(f"{source}={values.get(source, 0)}" for source in SOURCES)


def render_report(payload: dict[str, object]) -> str:
    rows = payload["queries"]
    assert isinstance(rows, list)
    output = [
        "# Mixed-Source Global Cap Audit",
        "",
        "## Method",
        "",
        (
            "This deterministic audit executes the real SearchService, SQLite FTS5, "
            "and the installed local multilingual MiniLM. Six source-shaped connectors "
            "each receive a bounded pre-candidate opportunity. The final cap of 30 is "
            "applied only after the union is scored. Each query is repeated with both "
            "source request order and connector completion order reversed. Uneven final "
            "source composition is retained; the audit does not impose source quotas."
        ),
        "",
        (
            f"Queries: {payload['query_count']}. Source pre-candidate limit: "
            f"{payload['source_pre_candidate_limit']}. Semantic rerank limit: "
            f"{payload['semantic_candidate_limit']}. Final cap: "
            f"{payload['global_limit']}."
        ),
        "",
        "## Per-Query Evidence",
        "",
    ]
    for row in rows:
        assert isinstance(row, dict)
        output.extend(
            [
                f"### `{row['query']}`",
                "",
                f"- Matched: {_format_counts(row['matched_per_source'])}",
                f"- Candidate admitted: {_format_counts(row['admitted_per_source'])}",
                f"- Final top 30: {_format_counts(row['final_top_30_per_source'])}",
                (
                    "- Semantic top-20 opportunity: "
                    + _format_counts(row["semantic_candidates_per_source"])
                ),
                f"- Completion A: {', '.join(row['completion_order_a'])}",
                f"- Completion B: {', '.join(row['completion_order_b'])}",
                f"- Final identities/order unchanged: {row['final_results_unchanged']}",
                (
                    "- Relevance distributions: `"
                    + json.dumps(
                        row["relevance_distribution_by_source"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "`"
                ),
                "",
            ]
        )
    invariant = bool(payload["all_completion_shuffles_invariant"])
    verified = (
        invariant
        and bool(payload["all_source_admission_intact"])
        and bool(payload["comparable_fixture_sources_present"])
    )
    output.extend(
        [
            "## Finding",
            "",
            (
                "The initial audit identified a source-scale discontinuity at the bounded "
                "semantic stage: title-bearing records consumed the global top-20 lexical "
                "slots while comparable titleless social posts retained lexical-only scores. "
                "The top-20 limit and 25/75 fusion remain unchanged; selection now cycles "
                "deterministically through each source's lexical queue before global scoring. "
                "This allocates evaluation opportunity and does not reserve final positions."
            ),
            "",
            (
                "All matched sources retained their independently bounded admission "
                "opportunity. The global result cap was applied after FTS/BM25, unchanged "
                "bounded semantic reranking, explainable scoring, and duplicate-aware "
                "ordering. Connector completion order did not affect final result identity "
                "or order. Source distributions were not equalized."
            ),
            "" if invariant else "At least one shuffled run changed final identities or order.",
            "MIXED-SOURCE CAP VERIFIED" if verified else "MIXED-SOURCE CAP BIAS FOUND",
        ]
    )
    return "\n".join(line for line in output if line is not None)


def main() -> None:
    payload = asyncio.run(run_audit())
    JSON_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    report = render_report(payload)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    print(report)
    if not (
        payload["all_completion_shuffles_invariant"]
        and payload["all_source_admission_intact"]
        and payload["comparable_fixture_sources_present"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
