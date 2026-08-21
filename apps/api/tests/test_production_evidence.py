from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.production_evidence import (
    _item_payload,
    assert_target_not_in_memory,
    known_item_metrics,
    select_known_cases,
)
from sqlalchemy.orm import Session

from mirsad_api.connectors import ConnectorItem
from mirsad_api.database import init_database, make_engine
from mirsad_api.models import ContentItem, Source
from mirsad_api.provenance import AcquisitionMode

ROOT = Path(__file__).resolve().parents[3]


def test_known_item_metrics_are_positive_target_metrics_not_precision() -> None:
    metrics = known_item_metrics(
        [
            {"live_request_completed": True, "final_rank": 1},
            {"live_request_completed": True, "final_rank": 8},
            {"live_request_completed": True, "final_rank": None},
            {"live_request_completed": False, "final_rank": None},
        ]
    )
    assert metrics["cases"] == 3
    assert metrics["known_item_recall_at_5"] == pytest.approx(1 / 3, abs=0.0001)
    assert metrics["known_item_recall_at_10"] == pytest.approx(2 / 3, abs=0.0001)
    assert "p_at_5" not in metrics


def test_known_item_selection_preserves_real_url_and_language() -> None:
    item = ConnectorItem(
        source="bluesky",
        external_id="at://did:plc:test/app.bsky.feed.post/1",
        canonical_url="https://bsky.app/profile/test/post/1",
        author="Tester",
        author_handle="tester.bsky.social",
        title=None,
        text="وزارة التخطيط أعلنت تقريراً عاماً جديداً بغداد",
        published_at=datetime.now(UTC),
        language="ar",
        acquisition_mode=AcquisitionMode.PUBLIC_API,
    )
    record = _item_payload(item, "بغداد")
    cases = select_known_cases([record], maximum=1)
    assert len(cases) == 1
    assert cases[0].target_url == item.canonical_url
    assert cases[0].language == "arabic"
    assert cases[0].query == "@tester.bsky.social"


def test_known_item_evaluation_rejects_seed_memory_leakage() -> None:
    engine = make_engine("sqlite:///:memory:")
    init_database(engine)
    with Session(engine) as db:
        source = Source(key="rss", name="RSS", kind="rss")
        db.add(source)
        db.flush()
        db.add(
            ContentItem(
                source_id=source.id,
                external_id="seed",
                canonical_url="https://example.com/seed",
                author=None,
                title="Seed",
                text="Seed",
                published_at=None,
                language="en",
                acquisition_mode="DIRECT_API",
                content_fingerprint="seed",
                raw_metadata={},
                normalized_title="seed",
                normalized_text="seed",
                normalized_author="",
            )
        )
        db.commit()
        with pytest.raises(RuntimeError, match="present before"):
            assert_target_not_in_memory(db, "https://example.com/seed")
        assert_target_not_in_memory(db, "https://example.com/not-seeded")


def test_startup_manages_enabled_local_searxng_without_exposing_configuration() -> None:
    start = (ROOT / "start.sh").read_text(encoding="utf-8")
    stop = (ROOT / "stop.sh").read_text(encoding="utf-8")
    assert "docker compose --profile mafer up -d searxng" in start
    assert "/search?q=MIRSAD&format=json" in start
    assert "direct/public sources remain available" in start
    assert "docker compose --profile mafer stop searxng" in stop


def test_startup_refuses_unmanaged_processes_on_owned_ports() -> None:
    start = (ROOT / "start.sh").read_text(encoding="utf-8")
    assert 'for port in 8000 5173' in start
    assert 'probe.bind(("127.0.0.1", int(sys.argv[1])))' in start
    assert "Startup refused: localhost port $port is already in use" in start
