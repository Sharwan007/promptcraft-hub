"""Remove the administrator PIN so a new one can be created on the next visit to /admin.

Only run this on your own computer. Prompts and other data are not touched.
"""
from __future__ import annotations

import sys

import _bootstrap  # noqa: F401
from sqlalchemy import delete

from app.core.config import get_settings
from app.database import models as m
from app.database.connection import session_scope
from app.database.migrations import run_migrations
from app.database.connection import get_engine


def main() -> int:
    get_settings()
    run_migrations(get_engine())
    answer = input("This removes the administrator PIN (a new one is requested at the next sign-in). Type YES to continue: ")
    if answer.strip() != "YES":
        print("Cancelled. Nothing was changed.")
        return 1
    with session_scope() as db:
        db.execute(delete(m.AdminCredential))
    print("[OK] The administrator PIN was removed. Open http://127.0.0.1:8000/admin to set a new one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
