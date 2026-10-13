"""Health check used by the launcher, tests and monitoring."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", summary="Application health")
def health(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # pragma: no cover - reported, never raised
        database = "unavailable"
    return {"status": "ok" if database == "ok" else "degraded", "app": settings.app_name, "version": settings.app_version,
            "database": database, "pid": os.getpid(), "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
