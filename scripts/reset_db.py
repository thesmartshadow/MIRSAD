from __future__ import annotations

from pathlib import Path

from mirsad_api.config import get_settings
from mirsad_api.database import SessionLocal, engine, init_database
from mirsad_api.mafer.configuration import ensure_configuration_snapshots
from mirsad_api.models import AuditEvent


def main() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        raise SystemExit("reset-db only supports the local SQLite database")
    engine.dispose()
    path = Path(settings.database_url.removeprefix("sqlite:///"))
    for candidate in (path, Path(f"{path}-shm"), Path(f"{path}-wal")):
        if candidate.exists():
            candidate.unlink()
    init_database()
    with SessionLocal() as db:
        ensure_configuration_snapshots(db)
        db.add(
            AuditEvent(
                event_type="index_rebuilt",
                message="Database and FTS index rebuilt",
                context={},
            )
        )
        db.commit()
    print(f"Reset database: {path}")


if __name__ == "__main__":
    main()
