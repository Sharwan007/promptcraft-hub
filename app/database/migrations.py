"""Safe internal migrations tracked in the ``schema_version`` table.

Rules: migrations are additive and run in order exactly once. The database is never
dropped or recreated. To change the schema later, append a new function to MIGRATIONS.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.database.models import Base, SchemaVersion

logger = logging.getLogger("promptcraft.migrations")


def _m001_baseline(conn: Connection) -> None:
    Base.metadata.create_all(conn)  # checkfirst: only creates missing tables


def _m002_usage_index(conn: Connection) -> None:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usage_type_created ON prompt_usage_events (event_type, created_at)"))


def _m003_custom_prompt_listing_index(conn: Connection) -> None:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_custom_listing ON custom_prompts (profile_id, archived)"))


def _m004_validation_log(conn: Connection) -> None:
    Base.metadata.create_all(conn)  # creates validation_error_log if it is missing (additive only)


MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "Baseline schema", _m001_baseline),
    (2, "Usage event composite index", _m002_usage_index),
    (3, "Custom prompt listing index", _m003_custom_prompt_listing_index),
    (4, "Validation error log table", _m004_validation_log),
]


def current_version(engine: Engine) -> int:
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")).first()
        if not exists:
            return 0
        row = conn.execute(text("SELECT MAX(version) FROM schema_version")).first()
        return int(row[0] or 0)


def run_migrations(engine: Engine) -> int:
    """Apply pending migrations, each in its own transaction. Returns the final version."""
    SchemaVersion.__table__.create(bind=engine, checkfirst=True)
    applied = current_version(engine)
    for version, description, func in MIGRATIONS:
        if version <= applied:
            continue
        logger.info("Applying migration %s: %s", version, description)
        with engine.begin() as conn:  # commits on success, rolls back on error
            func(conn)
            conn.execute(
                text("INSERT INTO schema_version (version, description, applied_at) VALUES (:v, :d, CURRENT_TIMESTAMP)"),
                {"v": version, "d": description},
            )
        applied = version
    return applied
