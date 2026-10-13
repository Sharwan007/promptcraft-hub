"""Favorite prompts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import Page
from app.schemas.prompt import PromptSummary
from app.services import prompt_service, search_service

router = APIRouter(prefix="/api/favorites", tags=["Favorites"])


@router.get("", response_model=Page[PromptSummary], summary="List and search favorites")
def list_favorites(q: str = "", category: str = "", difficulty: str = "", ai_tool: str = "", sort: str = "relevance",
                   page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=60), db: Session = Depends(get_db)):
    pid = prompt_service.get_profile(db).id
    f = search_service.PromptFilters(q=q, category=category, difficulty=difficulty, ai_tool=ai_tool, sort=sort, page=page,
                                     page_size=page_size, favorites_only=True, profile_id=pid)
    res = search_service.search_prompts(db, f)
    fav = prompt_service.favorite_ids(db, pid)
    res["items"] = [prompt_service.summary_dict(p, fav) for p in res["items"]]
    return res


@router.post("/{prompt_id}", status_code=201, summary="Add a prompt to favorites")
def add_favorite(prompt_id: int, db: Session = Depends(get_db)) -> dict:
    created = prompt_service.add_favorite(db, prompt_id)
    return {"prompt_id": prompt_id, "is_favorite": True, "created": created}


@router.delete("/{prompt_id}", summary="Remove a prompt from favorites")
def remove_favorite(prompt_id: int, db: Session = Depends(get_db)) -> dict:
    removed = prompt_service.remove_favorite(db, prompt_id)
    return {"prompt_id": prompt_id, "is_favorite": False, "removed": removed}
