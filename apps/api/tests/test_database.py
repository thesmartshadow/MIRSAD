from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mirsad_api.domains.deduplication import content_fingerprint
from mirsad_api.domains.query import fts_query, normalize_text, process_query
from mirsad_api.models import (
    ContentItem,
    DiscoveryObservation,
    DiscoveryRecord,
    Source,
)


def test_content_insert_populates_fts_index(db: Session) -> None:
    source = Source(key="test", name="Test", kind="fixture")
    db.add(source)
    db.flush()
    item = ContentItem(
        source_id=source.id,
        external_id="1",
        canonical_url="https://example.com/1",
        title="Public policy report",
        text="Detailed institutional public policy analysis.",
        language="en",
        content_fingerprint=content_fingerprint(
            "Public policy report", "Detailed institutional public policy analysis."
        ),
    )
    db.add(item)
    db.commit()
    match_count = db.execute(
        text("SELECT count(*) FROM content_fts WHERE content_fts MATCH :query"),
        {"query": '"policy"'},
    ).scalar_one()
    assert match_count == 1

    item.text = "Updated institutional transparency analysis."
    db.commit()
    assert (
        db.execute(
            text("SELECT count(*) FROM content_fts WHERE content_fts MATCH :query"),
            {"query": '"transparency"'},
        ).scalar_one()
        == 1
    )
    db.delete(item)
    db.commit()
    assert db.execute(text("SELECT count(*) FROM content_fts")).scalar_one() == 0


def test_external_content_uniqueness_constraint(db: Session) -> None:
    source = Source(key="unique", name="Unique", kind="fixture")
    db.add(source)
    db.flush()
    values = {
        "source_id": source.id,
        "external_id": "same",
        "canonical_url": "https://example.com/same",
        "text": "record",
        "language": "en",
        "content_fingerprint": content_fingerprint(None, "record"),
    }
    db.add(ContentItem(**values))
    db.commit()
    db.add(ContentItem(**values))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError("duplicate source/external ID must fail")
    assert db.scalar(select(func.count(ContentItem.id))) == 1


def test_sqlite_datetime_round_trip_is_aware_utc(db: Session) -> None:
    source = Source(key="time", name="Time", kind="fixture")
    db.add(source)
    db.flush()
    local_offset = datetime(2026, 8, 9, 15, 0, tzinfo=timezone(timedelta(hours=3)))
    item = ContentItem(
        source_id=source.id,
        external_id="aware",
        canonical_url="https://example.com/aware",
        text="Aware timestamp record",
        published_at=local_offset,
        language="en",
        content_fingerprint=content_fingerprint(None, "Aware timestamp record"),
    )
    db.add(item)
    db.commit()
    db.expire_all()

    restored = db.get(ContentItem, item.id)
    assert restored is not None
    assert restored.published_at is not None
    assert restored.published_at.tzinfo is UTC
    assert restored.published_at.utcoffset() == timedelta(0)
    assert restored.published_at.hour == 12


def test_arabic_normalized_fields_participate_in_fts(db: Session) -> None:
    source = Source(key="arabic-fts", name="Arabic FTS", kind="fixture")
    db.add(source)
    db.flush()
    title = "وزارة الصحة"
    body = "إعلان رسمي من الوزارة"
    db.add(
        ContentItem(
            source_id=source.id,
            external_id="arabic",
            canonical_url="https://example.com/arabic",
            title=title,
            text=body,
            language="ar",
            content_fingerprint=content_fingerprint(title, body),
            normalized_title=normalize_text(title),
            normalized_text=normalize_text(body),
            normalized_author="",
        )
    )
    db.commit()

    count = db.execute(
        text("SELECT count(*) FROM content_fts WHERE content_fts MATCH :query"),
        {"query": fts_query(process_query("وزاره الصحه"))},
    ).scalar_one()
    assert count == 1


def test_discovery_memory_is_canonical_and_observations_cascade(db: Session) -> None:
    record = DiscoveryRecord(
        platform="x",
        canonical_url="https://x.com/public/status/123456",
        content_type="post",
        canonical_content_id="123456",
        indexed_title="Public record",
        indexed_snippet="Indexed public snippet",
        acquisition_mode="WEB_INDEX",
        metadata_completeness=0.5,
        content_fingerprint="a" * 64,
    )
    db.add(record)
    db.flush()
    db.add(
        DiscoveryObservation(
            discovery_record_id=record.id,
            engine="brave",
            discovery_query="site:x.com public record",
            query_variant_id="variant-1",
        )
    )
    db.commit()

    duplicate = DiscoveryRecord(
        platform="x",
        canonical_url=record.canonical_url,
        content_type="post",
        canonical_content_id="123456",
        indexed_title=None,
        indexed_snippet=None,
        acquisition_mode="WEB_INDEX",
        metadata_completeness=0,
        content_fingerprint="b" * 64,
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    stored = db.scalar(
        select(DiscoveryRecord).where(
            DiscoveryRecord.canonical_url == "https://x.com/public/status/123456"
        )
    )
    assert stored is not None
    db.delete(stored)
    db.commit()
    assert db.scalar(select(func.count()).select_from(DiscoveryObservation)) == 0


def test_search_read_models_use_evidence_backed_ordering_indexes(db: Session) -> None:
    history_plan = " ".join(
        str(row)
        for row in db.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT * FROM search_sessions "
                "ORDER BY started_at DESC LIMIT 100"
            )
        )
    )
    results_plan = " ".join(
        str(row)
        for row in db.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT * FROM search_results "
                "WHERE search_session_id=:session_id ORDER BY rank"
            ),
            {"session_id": "fixture"},
        )
    )

    assert "ix_search_sessions_started_at" in history_plan
    assert "ix_search_result_session_rank" in results_plan
