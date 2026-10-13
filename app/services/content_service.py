"""Administration of categories, subcategories and tags."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.database import models as m
from app.utilities.text_utils import clean_text, slugify


def categories_with_counts(db: Session, include_archived: bool = True) -> list[dict]:
    q = (select(m.Category, func.count(m.Prompt.id)).outerjoin(m.Prompt, m.Prompt.category_id == m.Category.id)
         .group_by(m.Category.id).order_by(m.Category.sort_order, m.Category.name))
    if not include_archived:
        q = q.where(m.Category.archived.is_(False))
    out = []
    for c, n in db.execute(q).all():
        out.append({"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "icon": c.icon,
                    "sort_order": c.sort_order, "archived": c.archived, "prompt_count": n,
                    "subcategories": [{"id": s.id, "category_id": s.category_id, "name": s.name, "slug": s.slug} for s in c.subcategories]})
    return out


def save_category(db: Session, name: str, description: str = "", icon: str = "folder", sort_order: int = 0, category_id: int | None = None) -> m.Category:
    name = clean_text(name, 100)
    if len(name) < 2:
        raise ValidationFailed("Category name must be at least 2 characters.")
    dup = db.scalar(select(m.Category.id).where(func.lower(m.Category.name) == name.lower(), m.Category.id != (category_id or -1)))
    if dup:
        raise Conflict(f"A category named '{name}' already exists.")
    c = db.get(m.Category, category_id) if category_id else m.Category(slug=slugify(name, 110))
    if c is None:
        raise NotFound("Category not found.")
    c.name, c.description, c.icon, c.sort_order = name, clean_text(description, 500), clean_text(icon, 40) or "folder", sort_order
    if not category_id and db.scalar(select(m.Category.id).where(m.Category.slug == c.slug)):
        raise Conflict("A category with a similar name already exists.")
    db.add(c)
    db.commit()
    return c


def archive_category(db: Session, category_id: int, archived: bool) -> m.Category:
    c = db.get(m.Category, category_id)
    if c is None:
        raise NotFound("Category not found.")
    c.archived = archived
    db.commit()
    return c


def save_subcategory(db: Session, category_id: int, name: str, subcategory_id: int | None = None) -> m.Subcategory:
    cat = db.get(m.Category, category_id)
    if cat is None:
        raise ValidationFailed("The selected category does not exist.")
    name = clean_text(name, 100)
    if len(name) < 2:
        raise ValidationFailed("Subcategory name must be at least 2 characters.")
    if db.scalar(select(m.Subcategory.id).where(m.Subcategory.category_id == category_id, func.lower(m.Subcategory.name) == name.lower(),
                                                m.Subcategory.id != (subcategory_id or -1))):
        raise Conflict(f"'{name}' already exists in {cat.name}.")
    s = db.get(m.Subcategory, subcategory_id) if subcategory_id else m.Subcategory(category_id=category_id)
    if s is None:
        raise NotFound("Subcategory not found.")
    s.name, s.slug = name, slugify(name, 110)
    db.add(s)
    db.commit()
    return s


def delete_subcategory(db: Session, subcategory_id: int) -> None:
    s = db.get(m.Subcategory, subcategory_id)
    if s is None:
        raise NotFound("Subcategory not found.")
    used = db.scalar(select(func.count()).select_from(m.Prompt).where(m.Prompt.subcategory_id == s.id)) or 0
    if used:
        raise Conflict(f"{used} prompt(s) still use this subcategory. Move them first.")
    db.delete(s)
    db.commit()


def tags_with_counts(db: Session) -> list[dict]:
    rows = db.execute(select(m.Tag, func.count(m.PromptTag.prompt_id)).outerjoin(m.PromptTag).group_by(m.Tag.id).order_by(m.Tag.name)).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug, "prompt_count": n} for t, n in rows]


def rename_tag(db: Session, tag_id: int, name: str) -> m.Tag:
    t = db.get(m.Tag, tag_id)
    if t is None:
        raise NotFound("Tag not found.")
    name = clean_text(name, 60).lower()
    if len(name) < 2:
        raise ValidationFailed("Tag name must be at least 2 characters.")
    if db.scalar(select(m.Tag.id).where(m.Tag.slug == slugify(name, 60), m.Tag.id != tag_id)):
        raise Conflict(f"A tag named '{name}' already exists.")
    t.name, t.slug = name, slugify(name, 60)
    db.commit()
    return t


def create_tag(db: Session, name: str) -> m.Tag:
    name = clean_text(name, 60).lower()
    if len(name) < 2:
        raise ValidationFailed("Tag name must be at least 2 characters.")
    if db.scalar(select(m.Tag.id).where(m.Tag.slug == slugify(name, 60))):
        raise Conflict(f"A tag named '{name}' already exists.")
    t = m.Tag(name=name, slug=slugify(name, 60))
    db.add(t)
    db.commit()
    return t


def delete_tag(db: Session, tag_id: int) -> None:
    t = db.get(m.Tag, tag_id)
    if t is None:
        raise NotFound("Tag not found.")
    db.execute(m.PromptTag.__table__.delete().where(m.PromptTag.tag_id == tag_id))
    db.delete(t)
    db.commit()
