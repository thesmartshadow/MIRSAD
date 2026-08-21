from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mirsad_api.config import Settings
from mirsad_api.connectors import (
    BaseConnector,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    MockConnector,
)
from mirsad_api.domains.semantic import ClusterSemanticScores, SemanticScores
from mirsad_api.models import AuditEvent, ContentItem, SearchSession
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import get_search_response
from mirsad_api.services.search import SearchService


class FailingConnector(MockConnector):
    metadata = ConnectorMetadata(
        key="failing",
        name="Failing fixture",
        kind="test",
        base_url="mock://failing",
        confidence=50,
    )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        await super().search(query, limit=0, since=since)
        raise ConnectorError("failing", "fixture_failure", "Deterministic isolated failure")


class EmptyConnector(MockConnector):
    metadata = ConnectorMetadata(
        key="empty",
        name="Empty fixture",
        kind="test",
        base_url="mock://empty",
        confidence=50,
    )

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        return await super().search(query, limit=0, since=since)


class ItemConnector(BaseConnector):
    def __init__(
        self,
        key: str,
        items: list[ConnectorItem],
        *,
        honor_limit: bool = True,
        delay: float = 0,
    ):
        self.metadata = ConnectorMetadata(
            key=key, name=key, kind="fixture", base_url=f"https://{key}.example"
        )
        super().__init__()
        self.items = items
        self.honor_limit = honor_limit
        self.delay = delay

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, None

    async def search(self, query: str, *, limit: int, since: datetime | None = None):
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.items[:limit] if self.honor_limit else list(self.items)

    def normalize(self, payload):
        raise NotImplementedError


class FixtureSemanticRanker:
    def __init__(
        self,
        scores_by_title: dict[str, float] | None = None,
        *,
        unavailable: bool = False,
        cluster_pairs_by_title: set[frozenset[str]] | None = None,
    ):
        self.scores_by_title = scores_by_title or {}
        self.unavailable = unavailable
        self.cluster_pairs_by_title = cluster_pairs_by_title or set()

    def score(self, query, documents):
        if self.unavailable:
            return SemanticScores(
                scores={},
                similarities={},
                state="unavailable",
                model="fixture",
                model_version="1",
                query_type="MULTI_TERM_TOPIC",
                duration_ms=0.1,
                detail="Fixture semantic model unavailable",
            )
        scores = {
            document.key: self.scores_by_title.get(document.title or "", 50.0)
            for document in documents
        }
        return SemanticScores(
            scores=scores,
            similarities={key: (value / 50) - 1 for key, value in scores.items()},
            state="ready",
            model="fixture",
            model_version="1",
            query_type="MULTI_TERM_TOPIC",
            duration_ms=0.1,
        )

    def cluster_similarities(self, documents, pairs):
        if self.unavailable:
            return ClusterSemanticScores(
                similarities={},
                state="unavailable",
                model="fixture",
                model_version="1",
                duration_ms=0.1,
                candidate_pairs=len(pairs),
            )
        titles = {document.key: document.title or "" for document in documents}
        similarities = {
            pair: 0.9
            if frozenset((titles[pair[0]], titles[pair[1]]))
            in self.cluster_pairs_by_title
            else 0.4
            for pair in pairs
        }
        return ClusterSemanticScores(
            similarities=similarities,
            state="ready",
            model="fixture",
            model_version="1",
            duration_ms=0.1,
            candidate_pairs=len(pairs),
        )


def connector_item(
    source: str,
    external_id: str,
    title: str,
    text: str,
    *,
    language: str = "und",
    published_at: datetime | None = None,
) -> ConnectorItem:
    return ConnectorItem(
        source=source,
        external_id=external_id,
        canonical_url=f"https://{source}.example/{external_id}",
        author=None,
        title=title,
        text=text,
        published_at=published_at or datetime.now(UTC),
        language=language,
        raw_metadata={"source_type": "fixture"},
    )


@pytest.mark.asyncio
async def test_connector_failure_is_isolated_and_audited(db: Session, settings: Settings) -> None:
    connectors = {
        "mock": MockConnector(latency=0.03),
        "failing": FailingConnector(latency=0.03),
    }
    seed_database(db, connectors)
    service = SearchService(db, settings, connectors)
    started = time.perf_counter()
    session_id = await service.execute(
        SearchRequest(query="public policy", sources=["mock", "failing"], limit=3)
    )
    elapsed = time.perf_counter() - started
    session = db.get(SearchSession, session_id)
    assert session is not None
    assert session.status == "partial"
    assert session.result_count == 3
    assert session.warnings[0]["source"] == "failing"
    assert elapsed < 0.5
    # Bounded pre-candidates are persisted for FTS evaluation; the displayed set
    # remains capped independently.
    assert db.scalar(select(func.count(ContentItem.id))) == 5
    event_types = set(db.scalars(select(AuditEvent.event_type)).all())
    assert {"search_started", "connector_failed", "search_completed"} <= event_types


@pytest.mark.asyncio
async def test_repeated_search_reuses_external_content(db: Session, settings: Settings) -> None:
    connectors = {"mock": MockConnector()}
    seed_database(db, connectors)
    service = SearchService(db, settings, connectors)
    request = SearchRequest(query="same query", sources=["mock"], limit=2)
    await service.execute(request)
    second_session_id = await service.execute(request)
    assert db.scalar(select(func.count(ContentItem.id))) == 5
    assert get_search_response(db, second_session_id).session.result_count == 2
    assert db.scalar(select(func.count(SearchSession.id))) == 2


@pytest.mark.asyncio
async def test_no_matches_with_one_healthy_source_is_partial_not_failed(
    db: Session, settings: Settings
) -> None:
    connectors = {"empty": EmptyConnector(), "failing": FailingConnector()}
    seed_database(db, connectors)
    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="public policy", sources=list(connectors), limit=2)
    )
    session = db.get(SearchSession, session_id)
    assert session is not None
    assert session.status == "partial"
    assert session.result_count == 0


@pytest.mark.asyncio
async def test_language_filter_detects_unknown_content_before_filtering(
    db: Session, settings: Settings
) -> None:
    connector = ItemConnector(
        "language",
        [
            connector_item("language", "en", "Baghdad update", "Baghdad public report"),
            connector_item("language", "ar", "بغداد الآن", "تقرير عام من بغداد"),
        ],
    )
    connectors = {"language": connector}
    seed_database(db, connectors)

    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="بغداد", sources=["language"], language="ar", limit=10)
    )
    response = get_search_response(db, session_id)

    assert [item.external_id for item in response.results] == ["ar"]
    assert response.results[0].language == "ar"


@pytest.mark.asyncio
async def test_common_pipeline_rejects_known_old_results(db: Session, settings: Settings) -> None:
    connector = ItemConnector(
        "time",
        [
            connector_item(
                "time",
                "old",
                "Public policy archive",
                "Public policy report",
                language="en",
                published_at=datetime.now(UTC) - timedelta(days=400),
            )
        ],
    )
    connectors = {"time": connector}
    seed_database(db, connectors)

    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="public policy", sources=["time"], time_range="24h")
    )

    assert get_search_response(db, session_id).results == []


@pytest.mark.asyncio
async def test_global_candidate_limit_retains_strongest_lexical_matches(
    db: Session, settings: Settings
) -> None:
    connectors = {
        "a": ItemConnector(
            "a",
            [
                connector_item(
                    "a", "weak-a", "Daily update", "Public notices with unrelated policy context"
                )
            ],
        ),
        "b": ItemConnector(
            "b",
            [
                connector_item(
                    "b", "weak-b", "General bulletin", "Policy notes mention a public meeting"
                )
            ],
        ),
        "c": ItemConnector(
            "c",
            [connector_item("c", "strong", "Public policy", "Detailed institutional analysis")],
        ),
    }
    seed_database(db, connectors)

    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="public policy", sources=["a", "b", "c"], limit=2)
    )
    identities = {item.external_id for item in get_search_response(db, session_id).results}

    assert "strong" in identities


@pytest.mark.asyncio
async def test_global_result_cap_is_invariant_to_source_and_completion_order(
    db: Session, settings: Settings
) -> None:
    connectors = {
        source: ItemConnector(
            source,
            [
                connector_item(
                    source,
                    f"{source}-{index}",
                    f"Public policy evidence {source} {index}",
                    f"Public policy analysis with distinctive evidence number {index}.",
                )
                for index in range(4)
            ],
            delay=delay,
        )
        for source, delay in (("alpha", 0.06), ("beta", 0.03), ("gamma", 0.0))
    }
    seed_database(db, connectors)
    semantic_scores = {
        f"Public policy evidence {source} {index}": 95 - (source_index * 10 + index)
        for source_index, source in enumerate(("alpha", "beta", "gamma"))
        for index in range(4)
    }
    service = SearchService(db, settings, connectors, FixtureSemanticRanker(semantic_scores))

    first_id = await service.execute(
        SearchRequest(query="public policy", sources=["alpha", "beta", "gamma"], limit=5)
    )
    first_response = get_search_response(db, first_id)
    first_diagnostics = db.get(SearchSession, first_id).diagnostics

    connectors["alpha"].delay = 0
    connectors["beta"].delay = 0.03
    connectors["gamma"].delay = 0.06
    second_id = await service.execute(
        SearchRequest(query="public policy", sources=["gamma", "beta", "alpha"], limit=5)
    )
    second_response = get_search_response(db, second_id)
    second_diagnostics = db.get(SearchSession, second_id).diagnostics

    first_order = [(item.source, item.external_id) for item in first_response.results]
    second_order = [(item.source, item.external_id) for item in second_response.results]
    assert first_diagnostics["connector_completion_order"] == [
        "gamma",
        "beta",
        "alpha",
    ]
    assert second_diagnostics["connector_completion_order"] == [
        "alpha",
        "beta",
        "gamma",
    ]
    assert first_order == second_order
    assert first_diagnostics["candidate_admission"]["admitted_per_source"] == {
        "alpha": 4,
        "beta": 4,
        "gamma": 4,
    }
    assert sum(first_diagnostics["candidate_admission"]["final_top_per_source"].values()) == 5


@pytest.mark.asyncio
async def test_bounded_semantic_evaluation_gives_each_matched_source_an_opportunity(
    db: Session, settings: Settings
) -> None:
    source_keys = ["one", "two", "three", "four", "five"]
    connectors = {
        source: ItemConnector(
            source,
            [
                connector_item(
                    source,
                    f"{source}-{index}",
                    f"Climate adaptation report {index}",
                    "Climate adaptation evidence for local resilience planning.",
                )
                for index in range(8)
            ],
        )
        for source in source_keys
    }
    seed_database(db, connectors)
    session_id = await SearchService(
        db,
        settings,
        connectors,
        FixtureSemanticRanker(),
    ).execute(
        SearchRequest(query="climate adaptation", sources=source_keys, limit=10)
    )
    diagnostics = db.get(SearchSession, session_id).diagnostics

    assert diagnostics["ranking"]["semantic_candidate_selection"] == (
        "source_opportunity_round_robin"
    )
    assert diagnostics["ranking"]["semantic_candidates_per_source"] == {
        source: 4 for source in source_keys
    }


@pytest.mark.asyncio
async def test_duplicate_external_ids_from_one_connector_are_collected_once(
    db: Session, settings: Settings
) -> None:
    repeated = connector_item("repeat", "same", "Public policy", "Public policy report")
    connector = ItemConnector("repeat", [repeated, repeated], honor_limit=False)
    connectors = {"repeat": connector}
    seed_database(db, connectors)

    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(query="public policy", sources=["repeat"], limit=10)
    )

    assert get_search_response(db, session_id).session.result_count == 1


@pytest.mark.asyncio
async def test_semantic_reranker_orders_dense_lexical_collisions(
    db: Session, settings: Settings
) -> None:
    relevant_title = "Municipal water authority reservoir plan"
    collision_title = "Municipal water authority shoe promotion"
    connector = ItemConnector(
        "semantic",
        [
            connector_item(
                "semantic",
                "collision",
                collision_title,
                "Municipal water authority is repeated as a retail campaign phrase for shoes.",
            ),
            connector_item(
                "semantic",
                "relevant",
                relevant_title,
                "Municipal water authority publishes reservoir targets and conservation rules.",
            ),
        ],
    )
    connectors = {"semantic": connector}
    seed_database(db, connectors)
    ranker = FixtureSemanticRanker({relevant_title: 95, collision_title: 10})

    session_id = await SearchService(db, settings, connectors, ranker).execute(
        SearchRequest(query="municipal water authority", sources=["semantic"], limit=10)
    )
    response = get_search_response(db, session_id)
    diagnostics = db.get(SearchSession, session_id).diagnostics

    assert [item.external_id for item in response.results] == ["relevant", "collision"]
    assert response.results[0].explanation.semantic_relevance == 95
    assert diagnostics["ranking"]["semantic_state"] == "ready"


@pytest.mark.asyncio
async def test_semantic_failure_preserves_lexical_search_results(
    db: Session, settings: Settings
) -> None:
    connector = ItemConnector(
        "fallback",
        [
            connector_item(
                "fallback",
                "body",
                "General bulletin",
                "A complete public policy report from the institution.",
            ),
            connector_item(
                "fallback",
                "title",
                "Public policy report",
                "Detailed institutional findings and recommendations.",
            ),
        ],
    )
    connectors = {"fallback": connector}
    seed_database(db, connectors)

    session_id = await SearchService(
        db,
        settings,
        connectors,
        FixtureSemanticRanker(unavailable=True),
    ).execute(SearchRequest(query="public policy", sources=["fallback"], limit=10))
    response = get_search_response(db, session_id)
    diagnostics = db.get(SearchSession, session_id).diagnostics

    assert [item.external_id for item in response.results] == ["title", "body"]
    assert all(item.explanation.semantic_relevance is None for item in response.results)
    assert diagnostics["ranking"]["semantic_state"] == "unavailable"


@pytest.mark.asyncio
async def test_duplicate_copies_do_not_monopolize_best_match_top_results(
    db: Session, settings: Settings
) -> None:
    duplicate_text = "Climate adaptation plan establishes flood defenses and heat response."
    connectors = {
        key: ItemConnector(
            key,
            [connector_item(key, "copy", "Climate adaptation plan", duplicate_text)],
        )
        for key in ("copy_a", "copy_b", "copy_c")
    }
    connectors["distinct"] = ItemConnector(
        "distinct",
        [
            connector_item(
                "distinct",
                "assessment",
                "Climate adaptation risk assessment",
                "Climate adaptation analysis maps drought risk and vulnerable districts.",
            )
        ],
    )
    seed_database(db, connectors)
    ranker = FixtureSemanticRanker(
        {
            "Climate adaptation plan": 95,
            "Climate adaptation risk assessment": 90,
        }
    )

    session_id = await SearchService(db, settings, connectors, ranker).execute(
        SearchRequest(query="climate adaptation", sources=list(connectors), limit=10)
    )
    response = get_search_response(db, session_id)

    assert {item.external_id for item in response.results[:2]} == {"copy", "assessment"}
    assert response.session.unique_count == 2


@pytest.mark.asyncio
async def test_search_persists_explainable_semantic_story_cluster_diagnostics(
    db: Session, settings: Settings
) -> None:
    english_title = "OpenAI launches Orion model"
    arabic_title = "إطلاق نموذج Orion من OpenAI"
    connectors = {
        "news": ItemConnector(
            "news",
            [
                connector_item(
                    "news",
                    "orion-news",
                    english_title,
                    "OpenAI unveiled Orion for multilingual public documents.",
                ),
                connector_item(
                    "news",
                    "office",
                    "OpenAI opens Baghdad office",
                    "OpenAI announced a regional office and local hiring plan.",
                ),
            ],
        ),
        "social": ItemConnector(
            "social",
            [
                connector_item(
                    "social",
                    "orion-social",
                    arabic_title,
                    "أطلقت شركة OpenAI نموذج Orion متعدد اللغات للوثائق العامة.",
                    language="ar",
                )
            ],
        ),
    }
    seed_database(db, connectors)
    ranker = FixtureSemanticRanker(
        cluster_pairs_by_title={frozenset((english_title, arabic_title))}
    )

    session_id = await SearchService(db, settings, connectors, ranker).execute(
        SearchRequest(query="OpenAI", sources=list(connectors), limit=10)
    )
    response = get_search_response(db, session_id)
    diagnostics = db.get(SearchSession, session_id).diagnostics["clustering"]

    story = next(cluster for cluster in response.clusters if cluster.member_count == 2)
    assert story.source_distribution == {"news": 1, "social": 1}
    assert story.platform_diversity == 2
    assert diagnostics["strategy"] == "distinctive_blocks_complete_linkage"
    assert diagnostics["semantic_state"] == "ready"
    assert diagnostics["candidate_pairs"] >= 1
    assert diagnostics["multi_member_clusters"][0]["member_reasons"]


@pytest.mark.asyncio
async def test_identifier_lane_rejects_shared_cve_prefix_collisions(
    db: Session, settings: Settings
) -> None:
    connector = ItemConnector(
        "github",
        [
            connector_item(
                "github",
                "target",
                "Patch for CVE-2026-61371",
                "The repository preserves the complete vulnerability identifier.",
            ),
            connector_item(
                "github",
                "collision",
                "Patch for CVE-2026-64561",
                "A different vulnerability from the same year.",
            ),
        ],
    )
    connectors = {"github": connector}
    seed_database(db, connectors)

    session_id = await SearchService(db, settings, connectors).execute(
        SearchRequest(
            query="CVE-2026-61371",
            sources=["github"],
            source_selection="explicit",
            exact_phrase=True,
            time_range="all",
            limit=10,
        )
    )
    response = get_search_response(db, session_id)

    assert [item.external_id for item in response.results] == ["target"]
