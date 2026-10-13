"""Create/upgrade the SQLite schema and load seed data into EMPTY tables only.

Usage:  python scripts/initialize_database.py [--reseed]
--reseed  ignore the 'already seeded' markers (still only fills tables that are empty).
"""
from __future__ import annotations

import sys

import _bootstrap  # noqa: F401
from app.core.config import get_settings
from app.core.logging_config import setup_logging


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    settings.ensure_directories()
    try:
        from app.database.initialization import initialize_database, table_counts
        result = initialize_database(seed=True, ignore_seed_flags="--reseed" in sys.argv)
        counts = table_counts()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Database initialisation failed: {exc.__class__.__name__}.")
        print("        Check that the 'data' folder is writable and that no other program has locked the database file.")
        print(f"        Technical details are in: {settings.log_path / 'promptcraft.log'}")
        return 1
    print(f"[OK] Database ready (schema version {result['schema_version']}): {settings.database_path}")
    loaded = {k: v for k, v in result["seeded"].items() if v}
    print(f"[OK] Seed data loaded this run: {loaded}" if loaded else "[OK] Seed data already present; nothing was changed.")
    print(f"[OK] Prompts: {counts['prompts']} | Categories: {counts['categories']} | Lessons: {counts['learning_modules']} | "
          f"Examples: {counts['examples']} | Glossary: {counts['glossary_terms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
