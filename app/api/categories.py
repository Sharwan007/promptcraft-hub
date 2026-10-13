"""Categories, subcategories and tags."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, optional_admin, require_admin
from app.core.exceptions import Conflict, NotFound
from app.database import models as m
from app.schemas.category import CategoryIn, SubcategoryIn, TagIn
from app.schemas.common import Message
from app.services import content_service

router = APIRouter(tags=["Categories and tags"])


class ArchiveIn(BaseModel):
    archived: bool


@router.get("/api/categories", summary="List categories with prompt counts")
def list_categories(include_archived: bool = False, db: Session = Depends(get_db), is_admin: bool = Depends(optional_admin)) -> list[dict]:
    return content_service.categories_with_counts(db, include_archived=include_archived and is_admin)


@router.post("/api/categories", status_code=201, summary="Create a category (admin)")
def create_category(body: CategoryIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    c = content_service.save_category(db, body.name, body.description, body.icon, body.sort_order)
    return {"id": c.id, "name": c.name, "slug": c.slug}


@router.put("/api/categories/{category_id}", summary="Update a category (admin)")
def update_category(category_id: int, body: CategoryIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    c = content_service.save_category(db, body.name, body.description, body.icon, body.sort_order, category_id)
    return {"id": c.id, "name": c.name, "slug": c.slug}


@router.patch("/api/categories/{category_id}/archive", summary="Archive or restore a category (admin)")
def archive_category(category_id: int, body: ArchiveIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    c = content_service.archive_category(db, category_id, body.archived)
    return {"id": c.id, "archived": c.archived}


@router.delete("/api/categories/{category_id}", summary="Delete an empty category (admin)")
def delete_category(category_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    c = db.get(m.Category, category_id)
    if c is None:
        raise NotFound("Category not found.")
    used = db.scalar(select(func.count()).select_from(m.Prompt).where(m.Prompt.category_id == c.id)) or 0
    if used:
        raise Conflict(f"{used} prompt(s) still use this category.", hint="Move or delete those prompts first, or archive the category instead.")
    for sub in list(c.subcategories):  # an empty category's own subcategories go with it
        db.delete(sub)
    db.delete(c)
    db.commit()
    return Message(message="The category was deleted.")


@router.get("/api/subcategories", summary="List subcategories")
def list_subcategories(category_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    q = select(m.Subcategory).order_by(m.Subcategory.name)
    if category_id:
        q = q.where(m.Subcategory.category_id == category_id)
    return [{"id": s.id, "category_id": s.category_id, "name": s.name, "slug": s.slug} for s in db.scalars(q)]


@router.post("/api/subcategories", status_code=201, summary="Create a subcategory (admin)")
def create_subcategory(body: SubcategoryIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    s = content_service.save_subcategory(db, body.category_id, body.name)
    return {"id": s.id, "category_id": s.category_id, "name": s.name}


@router.put("/api/subcategories/{subcategory_id}", summary="Rename a subcategory (admin)")
def update_subcategory(subcategory_id: int, body: SubcategoryIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    s = content_service.save_subcategory(db, body.category_id, body.name, subcategory_id)
    return {"id": s.id, "category_id": s.category_id, "name": s.name}


@router.delete("/api/subcategories/{subcategory_id}", summary="Delete an unused subcategory (admin)")
def delete_subcategory(subcategory_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    content_service.delete_subcategory(db, subcategory_id)
    return Message(message="The subcategory was deleted.")


@router.get("/api/tags", summary="List tags with prompt counts")
def list_tags(db: Session = Depends(get_db)) -> list[dict]:
    return content_service.tags_with_counts(db)


@router.post("/api/tags", status_code=201, summary="Create a tag (admin)")
def create_tag(body: TagIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    t = content_service.create_tag(db, body.name)
    return {"id": t.id, "name": t.name, "slug": t.slug}


@router.put("/api/tags/{tag_id}", summary="Rename a tag (admin)")
def rename_tag(tag_id: int, body: TagIn, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> dict:
    t = content_service.rename_tag(db, tag_id, body.name)
    return {"id": t.id, "name": t.name, "slug": t.slug}


@router.delete("/api/tags/{tag_id}", summary="Delete a tag (admin)")
def delete_tag(tag_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin)) -> Message:
    content_service.delete_tag(db, tag_id)
    return Message(message="The tag was deleted.")
