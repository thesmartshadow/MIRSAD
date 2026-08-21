from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def make_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _configure_sqlite)
    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def create_fts_index(target_engine: Engine) -> None:
    recreated = False
    with target_engine.begin() as connection:
        exists = bool(
            connection.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_fts'")
            ).scalar_one_or_none()
        )
        columns = (
            {str(row[1]) for row in connection.execute(text("PRAGMA table_info(content_fts)"))}
            if exists
            else set()
        )
        recreated = not exists
        if exists and "normalized_title" not in columns:
            for trigger in ("content_items_ai", "content_items_ad", "content_items_au"):
                connection.execute(text(f'DROP TRIGGER IF EXISTS "{trigger}"'))
            connection.execute(text("DROP TABLE content_fts"))
            exists = False
            recreated = True
    statements = (
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
            title, text, author, normalized_title, normalized_text, normalized_author,
            content='content_items', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS content_items_ai AFTER INSERT ON content_items BEGIN
          INSERT INTO content_fts(
            rowid, title, text, author, normalized_title, normalized_text, normalized_author
          ) VALUES (
            new.id, new.title, new.text, new.author,
            new.normalized_title, new.normalized_text, new.normalized_author
          );
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS content_items_ad AFTER DELETE ON content_items BEGIN
          INSERT INTO content_fts(
            content_fts, rowid, title, text, author,
            normalized_title, normalized_text, normalized_author
          ) VALUES (
            'delete', old.id, old.title, old.text, old.author,
            old.normalized_title, old.normalized_text, old.normalized_author
          );
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS content_items_au AFTER UPDATE ON content_items BEGIN
          INSERT INTO content_fts(
            content_fts, rowid, title, text, author,
            normalized_title, normalized_text, normalized_author
          ) VALUES (
            'delete', old.id, old.title, old.text, old.author,
            old.normalized_title, old.normalized_text, old.normalized_author
          );
          INSERT INTO content_fts(
            rowid, title, text, author, normalized_title, normalized_text, normalized_author
          ) VALUES (
            new.id, new.title, new.text, new.author,
            new.normalized_title, new.normalized_text, new.normalized_author
          );
        END
        """,
    )
    with target_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        if recreated:
            connection.execute(text("INSERT INTO content_fts(content_fts) VALUES ('rebuild')"))


def apply_schema_migrations(target_engine: Engine) -> None:
    """Apply small additive migrations without requiring an external migration runtime."""
    if target_engine.dialect.name != "sqlite":
        return
    inspector = inspect(target_engine)
    additions = {
        "source_health": {
            "failure_category": "VARCHAR(40)",
            "http_status": "INTEGER",
            "last_latency_ms": "FLOAT NOT NULL DEFAULT 0",
            "last_result_count": "INTEGER NOT NULL DEFAULT 0",
            "last_normalized_count": "INTEGER NOT NULL DEFAULT 0",
            "last_malformed_count": "INTEGER NOT NULL DEFAULT 0",
        },
        "search_sessions": {
            "diagnostics": "JSON NOT NULL DEFAULT '{}'",
        },
        "content_items": {
            "author_handle": "VARCHAR(300)",
            "author_verified": "BOOLEAN",
            "hashtags": "JSON",
            "mentions": "JSON",
            "media_type": "VARCHAR(40)",
            "normalized_title": "TEXT NOT NULL DEFAULT ''",
            "normalized_text": "TEXT NOT NULL DEFAULT ''",
            "normalized_author": "TEXT NOT NULL DEFAULT ''",
            "acquisition_mode": "VARCHAR(30) NOT NULL DEFAULT 'DIRECT_API'",
        },
        "content_metrics": {
            "like_count": "INTEGER",
            "view_count": "INTEGER",
            "comment_count": "INTEGER",
            "share_count": "INTEGER",
            "repost_count": "INTEGER",
            "reaction_count": "INTEGER",
        },
        "clusters": {
            "platform_diversity": "INTEGER NOT NULL DEFAULT 1",
        },
        "connector_runs": {
            "fetched_result_count": "INTEGER NOT NULL DEFAULT 0",
            "schema_valid_count": "INTEGER NOT NULL DEFAULT 0",
            "query_match_count": "INTEGER NOT NULL DEFAULT 0",
            "time_eligible_count": "INTEGER NOT NULL DEFAULT 0",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "attempt_latencies_ms": "JSON NOT NULL DEFAULT '[]'",
            "circuit_breaker_state": "VARCHAR(20) NOT NULL DEFAULT 'closed'",
        },
        "search_results": {
            "acquisition_path": "VARCHAR(30)",
            "acquisition_paths": "JSON",
        },
    }
    with target_engine.begin() as connection:
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, declaration in columns.items():
                if name not in existing:
                    connection.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}')
                    )
        from .domains.query import normalize_text

        rows = connection.execute(
            text(
                "SELECT id, title, text, author FROM content_items "
                "WHERE normalized_title = '' OR normalized_text = '' OR normalized_author = ''"
            )
        ).mappings()
        updates = [
            {
                "id": row["id"],
                "title": normalize_text(str(row["title"] or "")),
                "text": normalize_text(str(row["text"] or "")),
                "author": normalize_text(str(row["author"] or "")),
            }
            for row in rows
        ]
        if updates:
            connection.execute(
                text(
                    "UPDATE content_items SET normalized_title=:title, normalized_text=:text, "
                    "normalized_author=:author WHERE id=:id"
                ),
                updates,
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_search_sessions_started_at "
                "ON search_sessions(started_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_search_result_session_rank "
                "ON search_results(search_session_id, rank)"
            )
        )


def init_database(target_engine: Engine = engine) -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(target_engine)
    apply_schema_migrations(target_engine)
    create_fts_index(target_engine)


def rebuild_fts_index(target_engine: Engine = engine) -> int:
    create_fts_index(target_engine)
    with target_engine.begin() as connection:
        connection.execute(text("INSERT INTO content_fts(content_fts) VALUES ('rebuild')"))
        return int(connection.execute(text("SELECT count(*) FROM content_fts")).scalar_one())


async def get_db() -> AsyncGenerator[Session, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
