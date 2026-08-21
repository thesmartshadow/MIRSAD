from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mirsad_api.config import Settings
from mirsad_api.database import init_database, make_engine


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def test_engine(database_url: str) -> Generator[Engine, None, None]:
    engine = make_engine(database_url)
    init_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)
    with factory() as session:
        yield session


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        enable_mock_connector=True,
        semantic_ranking_enabled=False,
    )
