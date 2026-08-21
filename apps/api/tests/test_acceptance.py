from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from mirsad_api.config import Settings
from mirsad_api.connectors import (
    BaseConnector,
    ConnectorError,
    ConnectorItem,
    ConnectorMetadata,
    YouTubeConnector,
)
from mirsad_api.schemas import SearchRequest
from mirsad_api.services.bootstrap import seed_database
from mirsad_api.services.read_models import get_search_response
from mirsad_api.services.search import SearchService


class AcceptanceConnector(BaseConnector):
    def __init__(
        self,
        key: str,
        items: list[ConnectorItem] | None = None,
        error: ConnectorError | None = None,
    ) -> None:
        self.metadata = ConnectorMetadata(
            key=key, name=f"Fixture {key}", kind="test", base_url=f"mock://{key}"
        )
        super().__init__()
        self.items = items or []
        self.error = error

    def validate_configuration(self) -> tuple[bool, str | None]:
        return True, "Acceptance fixture"

    async def search(
        self, query: str, *, limit: int, since: datetime | None = None
    ) -> list[ConnectorItem]:
        if self.error:
            raise self.error
        self.last_diagnostics.raw_result_count = len(self.items)
        self.last_diagnostics.normalized_result_count = len(self.items)
        return self.items[:limit]

    def normalize(self, payload):  # pragma: no cover - fixtures are already normalized
        raise NotImplementedError


def item(
    source: str,
    external_id: str,
    text: str,
    *,
    url: str | None = None,
    language: str = "en",
) -> ConnectorItem:
    return ConnectorItem(
        source=source,
        external_id=external_id,
        canonical_url=url or f"https://fixture.example/{external_id}",
        author="fixture",
        title=text,
        text=f"Detailed {text} record for deterministic acceptance validation.",
        published_at=datetime.now(UTC),
        language=language,
        raw_metadata={"source_type": "fixture"},
    )


async def execute(
    db: Session,
    settings: Settings,
    connectors: dict[str, BaseConnector],
    request: SearchRequest,
):
    seed_database(db, connectors)
    session_id = await SearchService(db, settings, connectors).execute(request)
    return get_search_response(db, session_id)


@pytest.mark.asyncio
async def test_acceptance_a_b_c_multi_source_arabic_and_exact_phrase(
    db: Session, settings: Settings
) -> None:
    connectors = {
        "one": AcceptanceConnector("one", [item("one", "1", "public policy")]),
        "two": AcceptanceConnector("two", [item("two", "2", "public policy")]),
        "arabic": AcceptanceConnector(
            "arabic", [item("arabic", "3", "وزارة الصحة", language="ar")]
        ),
    }
    english = await execute(
        db,
        settings,
        connectors,
        SearchRequest(query="public policy", sources=["one", "two"], exact_phrase=True),
    )
    assert english.session.status == "completed"
    assert english.session.result_count == 2
    arabic = await execute(
        db,
        settings,
        connectors,
        SearchRequest(query="وزاره الصحه", sources=["arabic"], language="ar"),
    )
    assert arabic.session.normalized_query == "وزاره الصحه"
    assert arabic.results[0].language == "ar"


@pytest.mark.asyncio
async def test_acceptance_d_e_f_g_h_failure_states(db: Session, settings: Settings) -> None:
    good = AcceptanceConnector("good", [item("good", "1", "public policy")])
    failed = AcceptanceConnector(
        "failed",
        error=ConnectorError("failed", "dns_network", "Fixture network failure", retryable=True),
    )
    limited = AcceptanceConnector(
        "limited",
        error=ConnectorError("limited", "rate_limited", "Fixture rate limit", status_code=429),
    )
    empty = AcceptanceConnector("empty")
    youtube = YouTubeConnector(api_key=None)
    connectors = {
        "good": good,
        "failed": failed,
        "limited": limited,
        "empty": empty,
        "youtube": youtube,
    }
    partial = await execute(
        db,
        settings,
        connectors,
        SearchRequest(query="public policy", sources=["good", "failed", "limited", "youtube"]),
    )
    assert partial.session.status == "partial"
    assert {warning.code for warning in partial.session.warnings} == {
        "dns_network",
        "rate_limited",
        "unconfigured",
    }
    no_results = await execute(
        db,
        settings,
        connectors,
        SearchRequest(query="rare query", sources=["empty"]),
    )
    assert no_results.session.status == "completed"
    assert no_results.session.result_count == 0
    all_failed = await execute(
        db,
        settings,
        connectors,
        SearchRequest(query="rare query", sources=["failed", "limited"]),
    )
    assert all_failed.session.status == "failed"


@pytest.mark.asyncio
async def test_acceptance_i_duplicate_heavy_group_is_preserved(
    db: Session, settings: Settings
) -> None:
    shared_url = "https://fixture.example/shared-story"
    connectors = {
        "left": AcceptanceConnector(
            "left", [item("left", "1", "shared public story", url=shared_url)]
        ),
        "right": AcceptanceConnector(
            "right", [item("right", "2", "shared public story", url=shared_url)]
        ),
    }
    response = await execute(
        db,
        settings,
        connectors,
        SearchRequest(query="shared public story", sources=["left", "right"]),
    )
    assert response.session.result_count == 2
    assert response.session.unique_count == 1
    assert all(result.duplicate_group_id for result in response.results)
    assert response.results[0].related_sources == ["left", "right"]
