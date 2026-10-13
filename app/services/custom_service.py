"""Custom ("My Prompts") CRUD with version history, archive and restore."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFound, ValidationFailed
from app.core.security import utcnow
from app.database import models as m
from app.schemas.prompt import CustomPromptIn
from app.services.prompt_service import get_profile, get_prompt
from app.utilities.text_utils import clean_text, escape_like, sanitize_search
from app.utilities.validation import normalize_tags


def to_dict(c: m.CustomPrompt) -> dict:
    return {"id": c.id, "title": c.title, "description": c.description, "content": c.content,
            "category_id": c.category_id, "category": c.category.name if c.category else None,
            "tags": c.tags or [], "source_prompt_id": c.source_prompt_id, "origin": c.origin, "version": c.version,
            "archived": c.archived, "created_at": c.created_at, "updated_at": c.updated_at}


def _category_check(db: Session, category_id: int | None) -> None:
    if category_id is not None and db.get(m.Category, category_id) is None:
        raise ValidationFailed("The selected category does not exist.")


def get_custom(db: Session, cid: int) -> m.CustomPrompt:
    c = db.get(m.CustomPrompt, cid)
    if c is None or c.profile_id != get_profile(db).id:
        raise NotFound("That custom prompt could not be found.")
    return c


def list_custom(db: Session, q: str = "", category_id: int | None = None, archived: bool = False, tag: str = "",
                page: int = 1, page_size: int = 20) -> dict:
    profile = get_profile(db)
    stmt = select(m.CustomPrompt).where(m.CustomPrompt.profile_id == profile.id, m.CustomPrompt.archived.is_(archived))
    q = sanitize_search(q)
    for term in q.split()[:6]:
        like = f"%{escape_like(term)}%"
        stmt = stmt.where(or_(m.CustomPrompt.title.ilike(like, escape="\\"), m.CustomPrompt.content.ilike(like, escape="\\"),
                              m.CustomPrompt.description.ilike(like, escape="\\")))
    if category_id:
        stmt = stmt.where(m.CustomPrompt.category_id == category_id)
    rows = list(db.scalars(stmt.order_by(m.CustomPrompt.updated_at.desc())).unique())
    if tag:
        rows = [r for r in rows if tag.lower() in [t.lower() for t in (r.tags or [])]]
    total = len(rows)
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    chunk = rows[(page - 1) * page_size: page * page_size]
    return {"items": [to_dict(r) for r in chunk], "total": total, "page": page, "page_size": page_size,
            "pages": max(1, -(-total // page_size))}


def _snapshot(c: m.CustomPrompt, note: str = "") -> m.CustomPromptVersion:
    return m.CustomPromptVersion(custom_prompt_id=c.id, version=c.version, title=c.title, description=c.description,
                                 content=c.content, tags=list(c.tags or []), change_note=clean_text(note, 200))


def create_custom(db: Session, data: CustomPromptIn) -> m.CustomPrompt:
    _category_check(db, data.category_id)
    if data.source_prompt_id is not None:
        get_prompt(db, data.source_prompt_id, include_hidden=True)
    c = m.CustomPrompt(profile_id=get_profile(db).id, title=clean_text(data.title, 200), description=clean_text(data.description, 1000),
                       content=clean_text(data.content), category_id=data.category_id, tags=normalize_tags(data.tags),
                       source_prompt_id=data.source_prompt_id, origin=clean_text(data.origin, 30) or "manual", version=1)
    try:
        db.add(c)
        db.flush()
        db.add(_snapshot(c, data.change_note or "Created"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_custom(db, c.id)


def update_custom(db: Session, cid: int, data: CustomPromptIn) -> m.CustomPrompt:
    c = get_custom(db, cid)
    _category_check(db, data.category_id)
    title, desc, content = clean_text(data.title, 200), clean_text(data.description, 1000), clean_text(data.content)
    tags = normalize_tags(data.tags)
    changed = (title, desc, content, tags) != (c.title, c.description, c.content, list(c.tags or []))
    try:
        c.category_id = data.category_id
        if changed:
            c.title, c.description, c.content, c.tags = title, desc, content, tags
            c.version += 1
            c.updated_at = utcnow()
            db.add(_snapshot(c, data.change_note or "Edited"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_custom(db, cid)


def set_archived(db: Session, cid: int, archived: bool) -> m.CustomPrompt:
    c = get_custom(db, cid)
    c.archived = archived
    c.updated_at = utcnow()
    db.commit()
    return c


def delete_permanently(db: Session, cid: int) -> None:
    c = get_custom(db, cid)
    db.delete(c)
    db.commit()


def versions(db: Session, cid: int) -> list[m.CustomPromptVersion]:
    get_custom(db, cid)
    return list(db.scalars(select(m.CustomPromptVersion).where(m.CustomPromptVersion.custom_prompt_id == cid)
                           .order_by(m.CustomPromptVersion.version.desc())))


def restore_version(db: Session, cid: int, version: int) -> m.CustomPrompt:
    c = get_custom(db, cid)
    v = db.scalar(select(m.CustomPromptVersion).where(m.CustomPromptVersion.custom_prompt_id == cid, m.CustomPromptVersion.version == version))
    if v is None:
        raise NotFound(f"Version {version} does not exist for this prompt.")
    try:
        c.title, c.description, c.content, c.tags = v.title, v.description, v.content, list(v.tags or [])
        c.version += 1
        c.updated_at = utcnow()
        db.add(_snapshot(c, f"Restored from version {version}"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return c


def duplicate_from_library(db: Session, prompt_id: int, filled_text: str | None = None) -> m.CustomPrompt:
    p = get_prompt(db, prompt_id)
    data = CustomPromptIn(title=f"{p.title} (my copy)"[:200], description=p.description, content=filled_text or p.full_prompt,
                          category_id=p.category_id, tags=[t.name for t in p.tags], source_prompt_id=p.id,
                          origin="library-copy", change_note="Duplicated from the library")
    return create_custom(db, data)


def counts(db: Session) -> dict:
    pid = get_profile(db).id
    active = db.scalar(select(func.count()).select_from(m.CustomPrompt).where(m.CustomPrompt.profile_id == pid, m.CustomPrompt.archived.is_(False))) or 0
    arch = db.scalar(select(func.count()).select_from(m.CustomPrompt).where(m.CustomPrompt.profile_id == pid, m.CustomPrompt.archived.is_(True))) or 0
    return {"active": active, "archived": arch}
