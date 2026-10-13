"""Settings and public statistics."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import ValidationFailed
from app.schemas.prompt import SettingsIn
from app.services import prompt_service, statistics_service
from app.utilities.text_utils import clean_text

router = APIRouter(prefix="/api", tags=["Settings and statistics"])


def _settings_dict(p) -> dict:
    return {"display_name": p.display_name, "role": p.role, "theme": p.theme, "default_ai_tool": p.default_ai_tool, "view_mode": p.view_mode}


@router.get("/settings", summary="Local profile and preferences")
def get_settings_api(db: Session = Depends(get_db)) -> dict:
    return _settings_dict(prompt_service.get_profile(db))


@router.put("/settings", summary="Update local profile and preferences")
def update_settings(body: SettingsIn, db: Session = Depends(get_db)) -> dict:
    name = clean_text(body.display_name, 80)
    if not name:
        raise ValidationFailed("Display name cannot be empty.")
    p = prompt_service.get_profile(db)
    p.display_name, p.role, p.theme = name, clean_text(body.role, 80), body.theme
    p.default_ai_tool, p.view_mode = body.default_ai_tool, body.view_mode
    db.commit()
    return _settings_dict(p)


@router.get("/statistics", summary="Library and learning statistics")
def statistics(db: Session = Depends(get_db)) -> dict:
    return statistics_service.dashboard_stats(db)
