"""Database initialisation: migrations + seed (only into empty tables)."""
from __future__ import annotations

import logging

from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.database.connection import get_engine, session_scope
from app.database.migrations import run_migrations
from app.database.models import LocalProfile

logger = logging.getLogger("promptcraft.init")


def ensure_profile() -> int:
    with session_scope() as db:
        profile = db.scalar(select(LocalProfile).order_by(LocalProfile.id).limit(1))
        if profile is None:
            profile = LocalProfile()
            db.add(profile)
            db.flush()
        return profile.id


def initialize_database(seed: bool = True, ignore_seed_flags: bool = False) -> dict:
    """Create/upgrade the schema and seed empty tables. Safe to call on every start."""
    settings = get_settings()
    settings.ensure_directories()
    engine = get_engine()
    try:
        version = run_migrations(engine)
        ensure_profile()
        counts = {}
        if seed:
            from app.seed.seed_database import seed_all
            with session_scope() as db:
                counts = seed_all(db, ignore_flags=ignore_seed_flags)
    except OperationalError as exc:
        logger.error("Database initialisation failed: %s", exc)
        raise
    logger.info("Database ready (schema v%s) at %s", version, settings.database_path.name)
    return {"schema_version": version, "seeded": counts}


def table_counts() -> dict:
    from app.database import models as m
    with session_scope() as db:
        return {
            "prompts": db.scalar(select(func.count()).select_from(m.Prompt)) or 0,
            "categories": db.scalar(select(func.count()).select_from(m.Category)) or 0,
            "examples": db.scalar(select(func.count()).select_from(m.BeforeAfterExample)) or 0,
            "learning_modules": db.scalar(select(func.count()).select_from(m.LearningModule)) or 0,
            "glossary_terms": db.scalar(select(func.count()).select_from(m.GlossaryTerm)) or 0,
            "featured": db.scalar(select(func.count()).select_from(m.Prompt).where(m.Prompt.featured.is_(True))) or 0,
        }
